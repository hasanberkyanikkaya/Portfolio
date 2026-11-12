"""Tests for the Sentiment report generation and the /sentiment endpoints (Phase 5).

Deterministic expectations come from conftest's make_closes() ramp (last close
125.90): sma252 = 113.35 -> vix pct_vs_avg 11.07 -> vix score 38.93;
sma125 = 119.70 -> momentum pct 5.18 -> momentum score 82.38; every basket
ramp ends at its window max -> 30 highs / 0 lows -> breadth score 100.00;
composite = (38.93 + 82.38 + 100.00) / 3 = 73.77 -> "greed".
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import DailyReport
from app.services.claude_client import ClaudeUnavailableError
from app.services.sentiment import (
    SENTIMENT_BASKET,
    breadth_score,
    classify_high_low,
    classify_sentiment,
    composite_score,
    generate_sentiment,
    momentum_score,
    vix_score,
)
from app.services.yahoo_client import YahooRateLimitError, YahooUnavailableError


@pytest.fixture(autouse=True)
def _no_fetch_delay(monkeypatch):
    """The polite inter-fetch spacing is real-Yahoo etiquette, not test material —
    without this every basket fetch adds ~7 s per test."""
    monkeypatch.setattr("app.services.sentiment.BASKET_FETCH_DELAY_SECONDS", 0)


async def _count_reports(session_factory) -> int:
    async with session_factory() as session:
        return (await session.execute(select(func.count(DailyReport.id)))).scalar_one()


# --- Endpoints ------------------------------------------------------------------


async def test_get_returns_404_when_no_report_exists(client):
    response = await client.get("/sentiment")
    assert response.status_code == 404


async def test_refresh_then_get_roundtrip(client, fake_claude):
    refresh = await client.post("/sentiment/refresh")
    assert refresh.status_code == 200

    latest = await client.get("/sentiment")
    assert latest.status_code == 200
    content = latest.json()["content"]
    assert content["text"] == "Fake report text"
    assert fake_claude.calls == 1

    data = content["data"]
    assert data["score"] == "73.77"
    assert data["label"] == "greed"
    assert data["components_used"] == 3

    assert data["vix"]["latest_close"] == "125.90"
    assert data["vix"]["avg_252"] == "113.35"
    assert data["vix"]["pct_vs_avg"] == "11.07"
    assert data["vix"]["score"] == "38.93"

    assert data["momentum"]["ma125"] == "119.70"
    assert data["momentum"]["pct_from_ma125"] == "5.18"
    assert data["momentum"]["score"] == "82.38"

    assert data["breadth"]["universe_size"] == 30
    assert data["breadth"]["new_highs"] == 30
    assert data["breadth"]["new_lows"] == 0
    assert data["breadth"]["net_ratio_pct"] == "100.00"
    assert data["breadth"]["score"] == "100.00"


async def test_refresh_twice_updates_single_row(client, fake_claude, session_factory):
    first = await client.post("/sentiment/refresh")
    second = await client.post("/sentiment/refresh")
    assert first.status_code == second.status_code == 200

    assert await _count_reports(session_factory) == 1
    assert fake_claude.calls == 2  # force=True regenerates
    assert second.json()["updated_at"] is not None


async def test_scheduler_path_returns_cached_report(
    session_factory, fake_yahoo, fake_claude
):
    """force=False (the scheduler's mode) must not re-call Claude on the same day."""
    async with session_factory() as session:
        first = await generate_sentiment(session, fake_yahoo, fake_claude)
        second = await generate_sentiment(session, fake_yahoo, fake_claude)
    assert fake_claude.calls == 1
    assert first.id == second.id


async def test_vix_failure_degrades_and_reweights(client, fake_yahoo):
    fake_yahoo.raise_for = {"^VIX"}

    response = await client.post("/sentiment/refresh")
    assert response.status_code == 200
    content = response.json()["content"]
    assert "candles_unavailable:^VIX" in content["warnings"]

    data = content["data"]
    assert data["vix"] is None
    assert data["components_used"] == 2
    # (82.38 + 100.00) / 2
    assert data["score"] == "91.19"
    assert data["label"] == "extreme_greed"


async def test_basket_failure_kills_breadth_only(client, fake_yahoo):
    fake_yahoo.raise_for = set(SENTIMENT_BASKET)

    response = await client.post("/sentiment/refresh")
    assert response.status_code == 200
    content = response.json()["content"]
    assert "breadth_universe_too_small" in content["warnings"]

    data = content["data"]
    assert data["breadth"] is None
    assert data["components_used"] == 2
    # (38.93 + 82.38) / 2
    assert data["score"] == "60.66"
    assert data["label"] == "greed"


async def test_rate_limit_aborts_basket_early(client, fake_yahoo):
    """A 429 mid-basket must stop the remaining fetches, not hammer Yahoo."""
    fake_yahoo.errors[SENTIMENT_BASKET[2]] = YahooRateLimitError("429 from Yahoo")

    response = await client.post("/sentiment/refresh")
    assert response.status_code == 200
    content = response.json()["content"]
    assert "breadth_aborted_rate_limit" in content["warnings"]
    assert "breadth_universe_too_small" in content["warnings"]

    # Symbols after the 429 were never requested.
    for symbol in SENTIMENT_BASKET[3:]:
        assert symbol not in fake_yahoo.calls
    # VIX + momentum still carry the report.
    data = content["data"]
    assert data["breadth"] is None
    assert data["components_used"] == 2
    assert data["score"] == "60.66"


async def test_total_data_blackout_returns_503_and_writes_nothing(
    client, fake_yahoo, fake_claude, session_factory
):
    fake_yahoo.raise_on_call = YahooUnavailableError("Yahoo Finance did not respond")

    response = await client.post("/sentiment/refresh")
    assert response.status_code == 503
    assert await _count_reports(session_factory) == 0
    assert fake_claude.calls == 0  # Claude is never asked about an empty payload


async def test_claude_failure_returns_503_and_writes_nothing(
    client, fake_claude, session_factory
):
    fake_claude.raise_on_call = ClaudeUnavailableError("Anthropic did not respond")
    response = await client.post("/sentiment/refresh")
    assert response.status_code == 503
    assert await _count_reports(session_factory) == 0


# --- Rule-based label -------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (Decimal("0"), "extreme_fear"),
        (Decimal("24.99"), "extreme_fear"),
        (Decimal("25"), "fear"),
        (Decimal("44.99"), "fear"),
        (Decimal("45"), "neutral"),
        (Decimal("55"), "neutral"),
        (Decimal("55.01"), "greed"),
        (Decimal("75"), "greed"),
        (Decimal("75.01"), "extreme_greed"),
        (Decimal("100"), "extreme_greed"),
    ],
)
def test_classify_sentiment(score, expected):
    assert classify_sentiment(score) == expected


# --- Score math -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pct_vs_avg", "expected"),
    [
        (Decimal("0"), Decimal("50.00")),  # VIX at its 1y mean
        (Decimal("11.07"), Decimal("38.93")),
        (Decimal("60"), Decimal("0.00")),  # clamped low
        (Decimal("-60"), Decimal("100.00")),  # clamped high
    ],
)
def test_vix_score(pct_vs_avg, expected):
    assert vix_score(pct_vs_avg) == expected


@pytest.mark.parametrize(
    ("pct_from_ma", "expected"),
    [
        (Decimal("0"), Decimal("50.00")),  # at the MA
        (Decimal("8"), Decimal("100.00")),  # full scale
        (Decimal("-8"), Decimal("0.00")),
        (Decimal("10"), Decimal("100.00")),  # clamped
        (Decimal("4"), Decimal("75.00")),
    ],
)
def test_momentum_score(pct_from_ma, expected):
    assert momentum_score(pct_from_ma) == expected


def test_classify_high_low_rising_ramp_is_high():
    closes = [Decimal("100") + Decimal("0.1") * i for i in range(260)]
    assert classify_high_low(closes) == "high"


def test_classify_high_low_falling_ramp_is_low():
    closes = [Decimal("126") - Decimal("0.1") * i for i in range(260)]
    assert classify_high_low(closes) == "low"


def test_classify_high_low_flat_series_is_neither():
    # Both the high and the low tolerance hold -> contradictory -> neither.
    assert classify_high_low([Decimal("100")] * 252) == "neither"


def test_classify_high_low_mid_range_is_neither():
    closes = [Decimal("100"), Decimal("200")] + [Decimal("150")] * 250
    assert classify_high_low(closes) == "neither"


def test_classify_high_low_within_one_pct_tolerance_counts():
    closes = [Decimal("150")] * 251 + [Decimal("200"), Decimal("198.5")]
    # 198.5 >= 200 * 0.99 = 198 -> still a "new high"
    assert classify_high_low(closes) == "high"


@pytest.mark.parametrize(
    ("net_ratio", "expected"),
    [
        (Decimal("0"), Decimal("50.00")),
        (Decimal("100"), Decimal("100.00")),
        (Decimal("-100"), Decimal("0.00")),
        (Decimal("20"), Decimal("60.00")),
    ],
)
def test_breadth_score(net_ratio, expected):
    assert breadth_score(net_ratio) == expected


def test_composite_score_averages():
    assert composite_score(
        [Decimal("38.93"), Decimal("82.38"), Decimal("100.00")]
    ) == Decimal("73.77")
    assert composite_score([Decimal("42.00")]) == Decimal("42.00")
