from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.timeutils import today_ny
from app.models import Prediction
from app.services.predictions import (
    build_algorithm_stats,
    evaluate_prediction,
    is_expired,
    predict_rsi_reversion,
    predict_swing_breakout,
    predict_trend_ma,
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


def to_candles(closes: list[Decimal], end: date = date(2026, 7, 10)) -> list[Candle]:
    return [
        Candle(date=end - timedelta(days=len(closes) - 1 - i), close=close)
        for i, close in enumerate(closes)
    ]


def make_prediction(
    ticker="AAPL",
    algorithm="trend_ma",
    prediction_date=date(2026, 6, 1),
    direction="up",
    price="100.00",
    status="pending",
) -> Prediction:
    return Prediction(
        ticker=ticker,
        algorithm=algorithm,
        prediction_date=prediction_date,
        predicted_direction=direction,
        price_at_prediction=Decimal(price),
        horizon_days=5,
        status=status,
    )


# --- Algorithms (pure) -------------------------------------------------------------


def test_trend_ma_up_on_ascending_ramp():
    assert predict_trend_ma(make_closes(60)) == "up"


def test_trend_ma_down_on_descending_ramp():
    assert predict_trend_ma(make_closes(60, Decimal("200"), Decimal("-0.5"))) == "down"


def test_trend_ma_none_on_flat_series():
    assert predict_trend_ma([Decimal("100")] * 60) is None


def test_trend_ma_none_on_short_history():
    assert predict_trend_ma(make_closes(49)) is None


def test_rsi_reversion_up_when_oversold():
    # All losses -> RSI 0 -> contrarian "up".
    assert predict_rsi_reversion(make_closes(20, Decimal("100"), Decimal("-1"))) == "up"


def test_rsi_reversion_down_when_overbought():
    # All gains -> RSI 100 -> "down".
    assert predict_rsi_reversion(make_closes(20, Decimal("100"), Decimal("1"))) == "down"


def test_rsi_reversion_none_in_neutral_zone():
    # Alternating equal up/down deltas -> RSI 50.
    closes = [Decimal("100") + Decimal(i % 2) for i in range(20)]
    assert predict_rsi_reversion(closes) is None


def test_rsi_reversion_none_on_short_history():
    assert predict_rsi_reversion(make_closes(14)) is None


def test_swing_breakout_up_above_prior_high():
    closes = [Decimal("100")] * 20 + [Decimal("101")]
    assert predict_swing_breakout(closes) == "up"


def test_swing_breakout_down_below_prior_low():
    closes = [Decimal("100")] * 20 + [Decimal("99")]
    assert predict_swing_breakout(closes) == "down"


def test_swing_breakout_none_inside_range():
    assert predict_swing_breakout([Decimal("100")] * 21) is None


def test_swing_breakout_none_on_short_history():
    assert predict_swing_breakout([Decimal("100")] * 20) is None


# --- Evaluation (pure) ---------------------------------------------------------------


def _eval_series(pd: date, closes_after: list[Decimal]) -> list[Candle]:
    """One candle ON prediction date (ignored) + one per following day."""
    series = [Candle(date=pd, close=Decimal("100"))]
    for i, close in enumerate(closes_after):
        series.append(Candle(date=pd + timedelta(days=i + 1), close=close))
    return series


def test_evaluate_up_correct():
    pd = date(2026, 6, 1)
    prediction = make_prediction(prediction_date=pd, direction="up", price="100.00")
    series = _eval_series(pd, [Decimal(str(100 + i)) for i in range(1, 7)])
    outcome, candle = evaluate_prediction(prediction, series)
    assert outcome == "correct"
    assert candle.date == pd + timedelta(days=5)  # the 5th trading day after


def test_evaluate_up_incorrect_when_lower():
    pd = date(2026, 6, 1)
    prediction = make_prediction(prediction_date=pd, direction="up", price="100.00")
    series = _eval_series(pd, [Decimal("99")] * 6)
    outcome, _ = evaluate_prediction(prediction, series)
    assert outcome == "incorrect"


def test_evaluate_equality_is_incorrect_for_both_directions():
    pd = date(2026, 6, 1)
    series = _eval_series(pd, [Decimal("100.00")] * 6)
    for direction in ("up", "down"):
        prediction = make_prediction(prediction_date=pd, direction=direction, price="100.00")
        outcome, _ = evaluate_prediction(prediction, series)
        assert outcome == "incorrect"


def test_evaluate_down_correct():
    pd = date(2026, 6, 1)
    prediction = make_prediction(prediction_date=pd, direction="down", price="100.00")
    series = _eval_series(pd, [Decimal("95")] * 6)
    outcome, _ = evaluate_prediction(prediction, series)
    assert outcome == "correct"


def test_evaluate_pending_with_too_few_later_candles():
    pd = date(2026, 6, 1)
    prediction = make_prediction(prediction_date=pd)
    series = _eval_series(pd, [Decimal("101")] * 4)  # only 4 candles after
    assert evaluate_prediction(prediction, series) is None


def test_evaluate_skips_weekend_gaps():
    # Candle dates with gaps (holidays/weekends): the 5th LATER CANDLE counts,
    # not the 5th calendar day.
    pd = date(2026, 6, 5)  # Friday
    dates = [date(2026, 6, 8), date(2026, 6, 9), date(2026, 6, 10),
             date(2026, 6, 11), date(2026, 6, 15)]  # gap over a weekend
    series = [Candle(date=pd, close=Decimal("100"))] + [
        Candle(date=d, close=Decimal("110")) for d in dates
    ]
    prediction = make_prediction(prediction_date=pd, direction="up", price="100.00")
    outcome, candle = evaluate_prediction(prediction, series)
    assert outcome == "correct"
    assert candle.date == date(2026, 6, 15)


def test_is_expired_boundary():
    today = date(2026, 7, 10)
    assert not is_expired(make_prediction(prediction_date=today - timedelta(days=30)), today)
    assert is_expired(make_prediction(prediction_date=today - timedelta(days=31)), today)


# --- Accuracy stats (pure) ------------------------------------------------------------


def test_stats_accuracy_excludes_pending_and_expired():
    rows = [
        make_prediction(status="correct"),
        make_prediction(status="correct"),
        make_prediction(status="incorrect"),
        make_prediction(status="pending"),
        make_prediction(status="expired"),
    ]
    stats = {s.algorithm: s for s in build_algorithm_stats(rows)}
    trend = stats["trend_ma"]
    assert (trend.total, trend.correct, trend.incorrect) == (5, 2, 1)
    assert (trend.pending, trend.expired) == (1, 1)
    assert trend.accuracy_pct == Decimal("66.67")


def test_stats_accuracy_none_when_nothing_decided():
    stats = build_algorithm_stats([make_prediction(status="pending")])
    assert all(s.accuracy_pct is None for s in stats)


# --- Cycle + endpoints -----------------------------------------------------------------


async def test_run_creates_predictions_and_dedupes(client, fake_yahoo):
    await create_position(client, "AAPL")
    fake_yahoo.closes["AAPL"] = make_closes()  # ascending ramp

    response = await client.post("/predictions/run")
    assert response.status_code == 200
    body = response.json()
    # Ramp fires all three: trend_ma up, rsi_reversion down (RSI 100),
    # swing_breakout up (new high every day).
    assert body["created"] == 3
    assert body["evaluated"] == 0
    assert "istatistiksel" in body["disclaimer"]

    rerun = await client.post("/predictions/run")
    assert rerun.status_code == 200
    assert rerun.json()["created"] == 0  # same candle day — clean no-op


async def test_run_evaluates_pending_for_removed_ticker(client, fake_yahoo, session_factory):
    # MSFT has a pending prediction but is NOT in the portfolio anymore —
    # it must still be fetched and evaluated.
    prediction = make_prediction(
        ticker="MSFT",
        prediction_date=today_ny() - timedelta(days=10),
        direction="up",
        price="1.00",
    )
    async with session_factory() as session:
        session.add(prediction)
        await session.commit()
    fake_yahoo.closes["MSFT"] = make_closes()

    response = await client.post("/predictions/run")
    assert response.status_code == 200
    assert response.json()["evaluated"] == 1
    assert "MSFT" in fake_yahoo.calls

    async with session_factory() as session:
        row = (await session.execute(select(Prediction))).scalar_one()
    assert row.status == "correct"  # ramp closes are all far above 1.00
    assert row.price_at_evaluation is not None
    assert row.actual_return_pct is not None
    assert row.evaluation_date == row.prediction_date + timedelta(days=5)


async def test_run_expires_stale_unfetchable_prediction(client, fake_yahoo, session_factory):
    prediction = make_prediction(
        ticker="ZZZZ", prediction_date=today_ny() - timedelta(days=40)
    )
    async with session_factory() as session:
        session.add(prediction)
        await session.commit()
    fake_yahoo.raise_for.add("ZZZZ")

    response = await client.post("/predictions/run")
    assert response.status_code == 200
    assert response.json()["expired"] == 1
    assert "candles_unavailable:ZZZZ" in response.json()["warnings"]

    async with session_factory() as session:
        row = (await session.execute(select(Prediction))).scalar_one()
    assert row.status == "expired"


async def test_run_empty_portfolio_is_valid(client):
    response = await client.post("/predictions/run")
    assert response.status_code == 200
    assert response.json() == {
        "created": 0, "evaluated": 0, "expired": 0,
        "warnings": [], "disclaimer": response.json()["disclaimer"],
    }


async def test_run_all_fetches_failed_503(client, fake_yahoo):
    await create_position(client, "AAPL")
    fake_yahoo.raise_on_call = YahooUnavailableError("down")
    response = await client.post("/predictions/run")
    assert response.status_code == 503


async def test_run_rate_limited_429(client, fake_yahoo):
    await create_position(client, "AAPL")
    fake_yahoo.raise_on_call = YahooRateLimitError("429")
    response = await client.post("/predictions/run")
    assert response.status_code == 429


async def test_summary_empty_db_is_200(client):
    response = await client.get("/predictions")
    assert response.status_code == 200
    body = response.json()
    assert body["predictions"] == []
    assert len(body["stats"]) == 3  # every algorithm appears, all zero
    assert all(s["accuracy_pct"] is None for s in body["stats"])
    assert "istatistiksel" in body["disclaimer"]


async def test_summary_after_run(client, fake_yahoo):
    await create_position(client, "AAPL")
    fake_yahoo.closes["AAPL"] = make_closes()
    await client.post("/predictions/run")

    response = await client.get("/predictions")
    assert response.status_code == 200
    body = response.json()
    assert len(body["predictions"]) == 3
    assert {p["ticker"] for p in body["predictions"]} == {"AAPL"}
    assert all(p["status"] == "pending" for p in body["predictions"])
    assert all(p["algorithm_name"] for p in body["predictions"])


async def test_ticker_endpoint_accuracy_and_404(client, session_factory):
    async with session_factory() as session:
        session.add(make_prediction(prediction_date=date(2026, 6, 1), status="correct"))
        session.add(make_prediction(prediction_date=date(2026, 6, 2), status="correct"))
        session.add(make_prediction(prediction_date=date(2026, 6, 3), status="incorrect"))
        await session.commit()

    response = await client.get("/predictions/aapl")  # case-insensitive
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    trend = next(s for s in body["stats"] if s["algorithm"] == "trend_ma")
    assert trend["accuracy_pct"] == "66.67"
    assert body["predictions"][0]["prediction_date"] == "2026-06-03"  # newest first

    missing = await client.get("/predictions/NVDA")
    assert missing.status_code == 404
