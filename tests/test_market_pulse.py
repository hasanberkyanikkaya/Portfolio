"""Tests for Market Pulse generation and the /market-pulse endpoints (Phase 4)."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import DailyReport
from app.services.claude_client import ClaudeUnavailableError
from app.services.finnhub_client import FinnhubUnavailableError
from app.services.market_pulse import (
    SECTOR_ETFS,
    classify_rsp_spy,
    generate_market_pulse,
    pct_distance,
    sma,
    weekly_change,
)
from app.services.yahoo_client import YahooUnavailableError
from tests.conftest import make_closes


async def _count_reports(session_factory) -> int:
    async with session_factory() as session:
        return (await session.execute(select(func.count(DailyReport.id)))).scalar_one()


def seed_quotes(fake_finnhub) -> None:
    """Quotes for all 14 daily-change symbols. RSP lags SPY by 0.60 points
    (breaches the 0.25 daily threshold) -> megacap_concentration; the identical
    candle ramps make the weekly gap exactly 0.00 (non-breaching)."""
    for symbol in [*SECTOR_ETFS, "RSP", "SPY"]:
        fake_finnhub.quotes[symbol] = Decimal("100.00")
        fake_finnhub.pct_changes[symbol] = Decimal("0.10")
    fake_finnhub.pct_changes["XLK"] = Decimal("1.50")
    fake_finnhub.pct_changes["XLE"] = Decimal("-2.00")
    fake_finnhub.pct_changes["RSP"] = Decimal("0.30")
    fake_finnhub.pct_changes["SPY"] = Decimal("0.90")


# --- Endpoints ------------------------------------------------------------------


async def test_get_returns_404_when_no_report_exists(client):
    response = await client.get("/market-pulse")
    assert response.status_code == 404


async def test_refresh_then_get_roundtrip(client, fake_finnhub, fake_claude):
    seed_quotes(fake_finnhub)
    refresh = await client.post("/market-pulse/refresh")
    assert refresh.status_code == 200

    latest = await client.get("/market-pulse")
    assert latest.status_code == 200
    content = latest.json()["content"]
    assert content["text"] == "Fake report text"
    assert fake_claude.calls == 1

    data = content["data"]
    assert len(data["sectors"]) == 12
    xlk = next(s for s in data["sectors"] if s["symbol"] == "XLK")
    assert xlk["daily_change_pct"] == "1.50"
    assert xlk["weekly_change_pct"] == "0.40"  # ramp: (125.9-125.4)/125.4*100

    rsp_spy = data["rsp_spy"]
    assert rsp_spy["daily_gap_pct"] == "-0.60"
    assert rsp_spy["signal"] == "megacap_concentration"

    ma = {row["symbol"]: row for row in data["ma_positioning"]}
    assert set(ma) == {"SPY", "QQQ"}
    assert ma["SPY"]["ma50"] == "123.45"
    assert ma["SPY"]["ma200"] == "115.95"
    assert ma["SPY"]["above_ma50"] is True
    assert ma["SPY"]["above_ma200"] is True
    assert ma["SPY"]["pct_from_ma50"] == "1.98"
    assert ma["SPY"]["pct_from_ma200"] == "8.58"


async def test_refresh_twice_updates_single_row(
    client, fake_finnhub, fake_claude, session_factory
):
    seed_quotes(fake_finnhub)
    first = await client.post("/market-pulse/refresh")
    second = await client.post("/market-pulse/refresh")
    assert first.status_code == second.status_code == 200

    assert await _count_reports(session_factory) == 1
    assert fake_claude.calls == 2  # force=True regenerates
    assert second.json()["updated_at"] is not None


async def test_scheduler_path_returns_cached_report(
    session_factory, fake_finnhub, fake_yahoo, fake_claude
):
    """force=False (the scheduler's mode) must not re-call Claude on the same day."""
    seed_quotes(fake_finnhub)
    async with session_factory() as session:
        first = await generate_market_pulse(session, fake_finnhub, fake_yahoo, fake_claude)
        second = await generate_market_pulse(session, fake_finnhub, fake_yahoo, fake_claude)
    assert fake_claude.calls == 1
    assert first.id == second.id


async def test_candle_failure_degrades_to_warnings(client, fake_finnhub, fake_yahoo):
    """A Yahoo outage kills weekly perf + MAs but the report still generates."""
    seed_quotes(fake_finnhub)
    fake_yahoo.raise_on_call = YahooUnavailableError("Yahoo Finance did not respond")

    response = await client.post("/market-pulse/refresh")
    assert response.status_code == 200
    content = response.json()["content"]
    assert "candles_unavailable:XLK" in content["warnings"]
    assert all(s["weekly_change_pct"] is None for s in content["data"]["sectors"])
    assert content["data"]["ma_positioning"] == []
    # Daily changes come from Finnhub and must survive.
    xlk = next(s for s in content["data"]["sectors"] if s["symbol"] == "XLK")
    assert xlk["daily_change_pct"] == "1.50"
    # The daily gap alone still yields a signal.
    assert content["data"]["rsp_spy"]["signal"] == "megacap_concentration"


async def test_total_data_blackout_returns_503_and_writes_nothing(
    client, fake_finnhub, fake_yahoo, fake_claude, session_factory
):
    fake_finnhub.raise_on_call = FinnhubUnavailableError("Finnhub did not respond")
    fake_yahoo.raise_on_call = YahooUnavailableError("Yahoo Finance did not respond")

    response = await client.post("/market-pulse/refresh")
    assert response.status_code == 503
    assert await _count_reports(session_factory) == 0
    assert fake_claude.calls == 0  # Claude is never asked about an empty payload


async def test_claude_failure_returns_503_and_writes_nothing(
    client, fake_finnhub, fake_claude, session_factory
):
    seed_quotes(fake_finnhub)
    fake_claude.raise_on_call = ClaudeUnavailableError("Anthropic did not respond")
    response = await client.post("/market-pulse/refresh")
    assert response.status_code == 503
    assert await _count_reports(session_factory) == 0


# --- Rule-based signal ------------------------------------------------------------


@pytest.mark.parametrize(
    ("daily_gap", "weekly_gap", "expected"),
    [
        (Decimal("0.25"), None, "broad_participation"),
        (None, Decimal("0.75"), "broad_participation"),
        (Decimal("-0.25"), None, "megacap_concentration"),
        (None, Decimal("-0.75"), "megacap_concentration"),
        (Decimal("0.24"), None, "neutral"),  # below threshold
        (Decimal("-0.10"), Decimal("0.10"), "neutral"),  # both small
        (Decimal("0.30"), Decimal("-0.80"), "neutral"),  # conflicting breaches
        (None, None, "neutral"),  # no data
    ],
)
def test_classify_rsp_spy(daily_gap, weekly_gap, expected):
    assert classify_rsp_spy(daily_gap, weekly_gap) == expected


# --- Decimal math -----------------------------------------------------------------


def test_math_on_deterministic_ramp():
    closes = make_closes()
    assert closes[-1] == Decimal("125.9")
    assert sma(closes, 50) == Decimal("123.45")
    assert sma(closes, 200) == Decimal("115.95")
    assert weekly_change(closes) == Decimal("0.40")
    assert pct_distance(Decimal("125.9"), Decimal("123.45")) == Decimal("1.98")
    assert pct_distance(Decimal("125.9"), Decimal("115.95")) == Decimal("8.58")


def test_weekly_change_needs_six_closes():
    assert weekly_change([Decimal("100")] * 5) is None
