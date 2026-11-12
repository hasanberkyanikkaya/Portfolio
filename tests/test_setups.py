from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import DailyReport
from app.services.claude_client import ClaudeRateLimitError, ClaudeUnavailableError
from app.services.setups import (
    RULE_NAMES,
    SetupItem,
    detect_setup,
    generate_setups,
    rsi,
    swing_low,
)
from app.services.yahoo_client import Candle, YahooRateLimitError, YahooUnavailableError

from .conftest import make_closes


@pytest.fixture(autouse=True)
def no_fetch_delay(monkeypatch):
    monkeypatch.setattr("app.services.technical.TICKER_FETCH_DELAY_SECONDS", 0)


async def create_position(client, ticker="AAPL", quantity="10", price="150.00"):
    response = await client.post(
        "/positions",
        json={"ticker": ticker, "quantity": quantity, "purchase_price": price},
    )
    assert response.status_code == 201
    return response


async def _count_reports(session_factory) -> int:
    async with session_factory() as session:
        return (await session.execute(select(func.count(DailyReport.id)))).scalar_one()


def to_candles(closes: list[Decimal]) -> list[Candle]:
    end = date(2026, 7, 10)
    return [
        Candle(date=end - timedelta(days=len(closes) - 1 - i), close=close)
        for i, close in enumerate(closes)
    ]


# Crafted close series (see each rule's math in services/setups.py):

# S1: 230-session ramp +0.5 (100 -> 214.5) then 13 sessions of -1.0 (-> 201.5).
# Exact values: ma50 206.02, ma200 170.57, RSI(14) ~23.5, swing_low_20 201.50.
S1_SERIES = make_closes(230, Decimal("100"), Decimal("0.5")) + [
    Decimal("214.5") - Decimal("1.0") * i for i in range(1, 14)
]

# S2: 200 flat sessions at 100, then a dip below MA200 and a fresh reclaim:
# 96 x6, 97, 98, 99, 100.5, 101, 101.5. MA200 today 99.87, close 101.50 (+1.63%).
S2_SERIES = [Decimal("100")] * 200 + [
    Decimal("96")] * 6 + [Decimal(s) for s in ("97", "98", "99", "100.5", "101", "101.5")
]

# S3: 200 sessions falling -0.5 (200 -> 100.5), 40 more falling (-> 80.5),
# then 20 sessions recovering +0.1 (-> 82.5). 52w low 80.50, 20 sessions old;
# RSI improved from ~0 at the low to ~40 now.
S3_SERIES = (
    make_closes(200, Decimal("200"), Decimal("-0.5"))
    + make_closes(40, Decimal("100"), Decimal("-0.5"))
    + make_closes(20, Decimal("80.6"), Decimal("0.1"))
)

# Geometry guard: like S1 but only 10 down sessions — S1 triggers, but the
# swing low sits inside the MA50 entry band, so stop >= entry_zone_low.
GUARD_SERIES = make_closes(230, Decimal("100"), Decimal("0.5")) + [
    Decimal("214.5") - Decimal("1.0") * i for i in range(1, 11)
]


# --- rsi (pure) ------------------------------------------------------------------


def test_rsi_all_gains_is_100():
    assert rsi(make_closes(30)) == Decimal("100.00")


def test_rsi_all_losses_is_0():
    assert rsi(make_closes(30, Decimal("100"), Decimal("-0.5"))) == Decimal("0.00")


def test_rsi_hand_computed_seed():
    # 8 gains of 1 then 6 losses of 1 -> seed-only Wilder RSI:
    # avg_gain 8/14, avg_loss 6/14, RS 4/3, RSI = 100 * 4/7 = 57.14.
    closes = [Decimal(100 + i) for i in range(9)] + [Decimal(108 - i) for i in range(1, 7)]
    assert len(closes) == 15
    assert rsi(closes) == Decimal("57.14")


def test_rsi_insufficient_history_is_none():
    assert rsi(make_closes(14)) is None


def test_swing_low_is_min_of_last_20():
    closes = make_closes(30) + [Decimal("90.5")]
    assert swing_low(closes) == Decimal("90.50")


# --- Rule detection (pure, via detect_setup) -----------------------------------------


def test_s1_rsi_oversold_ma50_fires():
    item = detect_setup("AAPL", to_candles(S1_SERIES))
    assert item is not None
    assert item.rule_id == "rsi_oversold_ma50"
    assert item.rule_name == RULE_NAMES["rsi_oversold_ma50"]
    assert item.close == Decimal("201.50")
    assert item.ma50 == Decimal("206.02")
    assert item.ma200 == Decimal("170.57")
    assert item.entry_zone_low == Decimal("201.90")  # ma50 * 0.98
    assert item.entry_zone_high == Decimal("210.14")  # ma50 * 1.02
    assert item.swing_low_20 == Decimal("201.50")
    assert item.stop_loss == Decimal("199.49")  # swing low * 0.99
    assert item.rsi_14 is not None and item.rsi_14 <= Decimal("35")
    assert "201.50" in item.rationale and "206.02" in item.rationale


def test_s2_ma200_reclaim_fires():
    item = detect_setup("AAPL", to_candles(S2_SERIES))
    assert item is not None
    assert item.rule_id == "ma200_reclaim"
    assert item.close == Decimal("101.50")
    assert item.ma200 == Decimal("99.87")
    assert item.entry_zone_low == Decimal("99.87")  # the reclaimed MA200
    assert item.entry_zone_high == Decimal("101.50")  # current close
    assert item.swing_low_20 == Decimal("96.00")
    assert item.stop_loss == Decimal("95.04")


def test_s2_extended_reclaim_does_not_fire():
    # Same shape but the last close is >3% above MA200 — chased, not fresh.
    series = S2_SERIES[:-1] + [Decimal("103")]
    assert detect_setup("AAPL", to_candles(series)) is None


def test_s3_low_rsi_divergence_fires():
    item = detect_setup("AAPL", to_candles(S3_SERIES))
    assert item is not None
    assert item.rule_id == "low_rsi_divergence"
    assert item.close == Decimal("82.50")
    assert item.low_52w == Decimal("80.50")
    assert item.entry_zone_low == Decimal("80.50")
    assert item.entry_zone_high == Decimal("82.50")
    assert item.stop_loss == Decimal("79.70")  # 52w low * 0.99
    assert item.rsi_14 is not None and item.rsi_14 <= Decimal("50")


def test_s3_low_made_today_does_not_fire():
    # Monotone decline: the 52w low IS the last close — no divergence to read.
    series = make_closes(260, Decimal("200"), Decimal("-0.4"))
    assert detect_setup("AAPL", to_candles(series)) is None


def test_geometry_guard_discards_stop_inside_entry_band():
    # S1 triggers but stop (swing low * 0.99) >= entry_zone_low (ma50 * 0.98).
    assert detect_setup("AAPL", to_candles(GUARD_SERIES)) is None


def test_no_setup_on_plain_uptrend():
    # The default conftest ramp: RSI 100, nowhere near MA50 — nothing fires.
    assert detect_setup("AAPL", to_candles(make_closes())) is None


def test_insufficient_history_yields_no_setup():
    assert detect_setup("AAPL", to_candles(make_closes(60))) is None


def test_rule_priority_first_match_wins(monkeypatch):
    def stub(rule_id):
        def check(ticker, closes, as_of):
            return SetupItem(
                ticker=ticker, rule_id=rule_id, rule_name=RULE_NAMES[rule_id],
                close=Decimal("100"), as_of=as_of,
                entry_zone_low=Decimal("99"), entry_zone_high=Decimal("101"),
                stop_loss=Decimal("95"), rsi_14=None, ma50=None, ma200=None,
                low_52w=None, swing_low_20=None, rationale="stub",
            )
        return check

    import app.services.setups as setups_module

    monkeypatch.setattr(
        setups_module,
        "_RULE_CHECKS",
        (stub("rsi_oversold_ma50"), stub("ma200_reclaim")),
    )
    item = detect_setup("AAPL", to_candles(make_closes()))
    assert item is not None and item.rule_id == "rsi_oversold_ma50"


# --- Endpoints ---------------------------------------------------------------------


async def test_get_returns_404_when_no_report_exists(client):
    response = await client.get("/portfolio/setups")
    assert response.status_code == 404


async def test_refresh_then_get_roundtrip(client, fake_yahoo, fake_claude):
    await create_position(client, ticker="AAPL")
    fake_yahoo.closes["AAPL"] = S1_SERIES

    refresh = await client.post("/portfolio/setups/refresh")
    assert refresh.status_code == 200
    assert fake_claude.calls == 1

    response = await client.get("/portfolio/setups")
    assert response.status_code == 200
    content = response.json()["content"]
    assert content["text"] == "Fake report text"

    data = content["data"]
    assert data["positions_scanned"] == 1
    setup = data["setups"][0]
    assert setup["ticker"] == "AAPL"
    assert setup["rule_id"] == "rsi_oversold_ma50"
    # Decimals are serialized as strings (json.dumps(default=str) convention).
    assert setup["entry_zone_low"] == "201.90"
    assert setup["entry_zone_high"] == "210.14"
    assert setup["stop_loss"] == "199.49"
    assert setup["close"] == "201.50"


async def test_refresh_twice_upserts_single_row(client, fake_claude, session_factory):
    await create_position(client, ticker="AAPL")
    first = await client.post("/portfolio/setups/refresh")
    second = await client.post("/portfolio/setups/refresh")
    assert first.status_code == second.status_code == 200
    assert await _count_reports(session_factory) == 1
    assert fake_claude.calls == 2  # force=True regenerates


async def test_scheduler_path_returns_cached_report(
    session_factory, fake_yahoo, fake_claude
):
    """force=False (the scheduler's mode) must not re-call Claude on the same day."""
    async with session_factory() as session:
        await generate_setups(session, fake_yahoo, fake_claude)
        await generate_setups(session, fake_yahoo, fake_claude)
    assert fake_claude.calls == 1


async def test_empty_portfolio_is_a_valid_report(client, fake_claude):
    response = await client.post("/portfolio/setups/refresh")
    assert response.status_code == 200
    content = response.json()["content"]
    assert content["data"]["positions_scanned"] == 0
    assert content["data"]["setups"] == []
    assert "empty_portfolio" in content["warnings"]
    assert fake_claude.calls == 1  # the "nothing to scan" narration is the product


async def test_no_setups_is_a_valid_report(client, fake_claude):
    # Default ramp closes -> no rule fires; Claude still narrates the empty scan.
    await create_position(client, ticker="AAPL")
    response = await client.post("/portfolio/setups/refresh")
    assert response.status_code == 200
    data = response.json()["content"]["data"]
    assert data["positions_scanned"] == 1
    assert data["setups"] == []
    assert fake_claude.calls == 1


async def test_all_tickers_failed_returns_503_and_writes_nothing(
    client, fake_yahoo, fake_claude, session_factory
):
    await create_position(client, ticker="AAPL")
    fake_yahoo.raise_on_call = YahooUnavailableError("Yahoo down")
    response = await client.post("/portfolio/setups/refresh")
    assert response.status_code == 503
    assert await _count_reports(session_factory) == 0
    assert fake_claude.calls == 0


async def test_rate_limited_returns_429(client, fake_yahoo):
    await create_position(client, ticker="AAPL")
    fake_yahoo.raise_on_call = YahooRateLimitError("429")
    response = await client.post("/portfolio/setups/refresh")
    assert response.status_code == 429


async def test_partial_failure_degrades_with_warning(client, fake_yahoo):
    await create_position(client, ticker="AAPL")
    await create_position(client, ticker="MSFT")
    fake_yahoo.raise_for = {"MSFT"}

    response = await client.post("/portfolio/setups/refresh")
    assert response.status_code == 200
    content = response.json()["content"]
    assert "candles_unavailable:MSFT" in content["warnings"]
    assert content["data"]["positions_scanned"] == 1


async def test_claude_failure_returns_503_and_writes_nothing(
    client, fake_claude, session_factory
):
    await create_position(client, ticker="AAPL")
    fake_claude.raise_on_call = ClaudeUnavailableError("Anthropic did not respond")
    response = await client.post("/portfolio/setups/refresh")
    assert response.status_code == 503
    assert await _count_reports(session_factory) == 0


async def test_claude_rate_limit_returns_429(client, fake_claude):
    await create_position(client, ticker="AAPL")
    fake_claude.raise_on_call = ClaudeRateLimitError("429")
    response = await client.post("/portfolio/setups/refresh")
    assert response.status_code == 429
