"""Predictions — rule-based direction calls with a logged, auditable track record (Phase 8).

Every trading day (17:10 ET job, or POST /predictions/run) each algorithm below
scans every unique portfolio ticker's Yahoo daily closes (shared per-NY-day memo
cache with services/technical.py). A firing algorithm logs ONE row to the
`predictions` table; `horizon_days` (5) trading days later the row is evaluated
against the actual close and marked correct/incorrect. No Claude anywhere —
the whole point is a mechanically verifiable track record.

ALGORITHMS (all run independently per ticker — no priority, they compete and
each accumulates its own accuracy stats). Directions are `up`/`down` only:
a "neutral" prediction is unfalsifiable under close-vs-close evaluation, so
when conditions aren't met the algorithm simply emits nothing that day.

A1 `trend_ma` — MA20/MA50 trend uyumu (needs >= MA_LONG closes)
   close > MA20 AND MA20 > MA50  -> up   (full bullish alignment)
   close < MA20 AND MA20 < MA50  -> down
A2 `rsi_reversion` — RSI aşırı alım/satım dönüşü (needs >= RSI period + 1 closes)
   RSI(14) <= RSI_BUY (30)   -> up   (contrarian: oversold tends to bounce)
   RSI(14) >= RSI_SELL (70)  -> down
A3 `swing_breakout` — 20 seans salınım kırılımı (needs >= SWING_WINDOW + 1 closes)
   prior = last SWING_WINDOW (20) closes EXCLUDING today
   close > max(prior) -> up   (breakout above the swing high)
   close < min(prior) -> down

PREDICTION DATE / DEDUPE: `prediction_date` is the LAST YAHOO CANDLE's date,
not today_ny() — it aligns evaluation with candle indices and makes holiday
reruns natural no-ops. One row per (ticker, algorithm, prediction_date),
enforced by a DB unique constraint + select-before-insert.

EVALUATION (holiday-robust, candle-date based): take the candles strictly
after prediction_date; once at least `horizon_days` exist, evaluate against
the `horizon_days`-th one. `up` is correct iff eval close > entry close,
`down` iff <; exact equality is INCORRECT for both (the predicted move did
not happen). Deliberately NO flat-band void: a void band would silently
shrink the accuracy denominator — instead `actual_return_pct` is stored on
every evaluated row so a +0.05% "correct" is visible for what it is.

EXPIRY: a pending row older than EVALUATION_EXPIRY_DAYS (30 calendar days)
that still can't be evaluated (persistent fetch failure, delisting, too few
later candles) becomes `expired` and is excluded from the accuracy
denominator. This also bounds how long we keep fetching tickers that left
the portfolio — pending rows for removed tickers ARE still fetched and
evaluated until they resolve or expire.

Degradation mirrors setups: per-ticker Yahoo failures degrade with
`candles_unavailable:{t}` warnings; only when portfolio tickers exist and
EVERY fetch failed does the cycle raise PredictionsDataUnavailableError
(rate_limited decides 429 vs 503). All math is Decimal via pnl.money.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Callable, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.timeutils import today_ny
from app.models import Position, Prediction
from app.schemas.predictions import AlgorithmStats
from app.services.market_pulse import pct_distance, sma
from app.services.pnl import money
from app.services.setups import rsi
from app.services.technical import fetch_daily_closes_cached
from app.services.yahoo_client import Candle, get_yahoo_client

logger = logging.getLogger(__name__)

# --- Tunables (see the module docstring for what each one does) ------------------
MA_SHORT = 20
MA_LONG = 50
RSI_BUY = Decimal("30")
RSI_SELL = Decimal("70")
SWING_WINDOW = 20
HORIZON_TRADING_DAYS = 5
EVALUATION_EXPIRY_DAYS = 30

ALGORITHM_NAMES: dict[str, str] = {
    "trend_ma": "MA20/MA50 trend uyumu",
    "rsi_reversion": "RSI aşırı alım/satım dönüşü",
    "swing_breakout": "20 seans salınım kırılımı",
}

Direction = Literal["up", "down"]


class PredictionsDataUnavailableError(Exception):
    """Portfolio tickers exist but every ticker's Yahoo fetch failed."""

    def __init__(self, rate_limited: bool) -> None:
        self.rate_limited = rate_limited
        super().__init__(
            "Yahoo rate limit hit before any ticker could be fetched"
            if rate_limited
            else "No historical data available for any portfolio ticker"
        )


# --- Algorithms (pure, unit-testable) ---------------------------------------------


def predict_trend_ma(closes: list[Decimal]) -> Direction | None:
    if len(closes) < MA_LONG:
        return None
    close = closes[-1]
    ma_short = sma(closes, MA_SHORT)
    ma_long = sma(closes, MA_LONG)
    if close > ma_short and ma_short > ma_long:
        return "up"
    if close < ma_short and ma_short < ma_long:
        return "down"
    return None


def predict_rsi_reversion(closes: list[Decimal]) -> Direction | None:
    rsi_14 = rsi(closes)
    if rsi_14 is None:
        return None
    if rsi_14 <= RSI_BUY:
        return "up"
    if rsi_14 >= RSI_SELL:
        return "down"
    return None


def predict_swing_breakout(closes: list[Decimal]) -> Direction | None:
    if len(closes) < SWING_WINDOW + 1:
        return None
    close = closes[-1]
    prior = closes[-(SWING_WINDOW + 1) : -1]
    if close > max(prior):
        return "up"
    if close < min(prior):
        return "down"
    return None


ALGORITHMS: dict[str, Callable[[list[Decimal]], Direction | None]] = {
    "trend_ma": predict_trend_ma,
    "rsi_reversion": predict_rsi_reversion,
    "swing_breakout": predict_swing_breakout,
}


# --- Evaluation (pure, unit-testable) ----------------------------------------------


def evaluate_prediction(
    prediction: Prediction, series: list[Candle]
) -> tuple[Literal["correct", "incorrect"], Candle] | None:
    """Outcome + the evaluation candle, or None while not yet evaluable."""
    candidates = [c for c in series if c.date > prediction.prediction_date]
    if len(candidates) < prediction.horizon_days:
        return None
    eval_candle = candidates[prediction.horizon_days - 1]
    eval_close = money(eval_candle.close)
    entry = prediction.price_at_prediction
    if prediction.predicted_direction == "up":
        outcome = "correct" if eval_close > entry else "incorrect"
    else:
        outcome = "correct" if eval_close < entry else "incorrect"
    return outcome, eval_candle


def is_expired(prediction: Prediction, today: date) -> bool:
    return (today - prediction.prediction_date).days > EVALUATION_EXPIRY_DAYS


# --- Accuracy stats (pure, unit-testable) --------------------------------------------


def build_algorithm_stats(predictions: list[Prediction]) -> list[AlgorithmStats]:
    """Per-algorithm counters + accuracy. Every algorithm always appears (a
    zero row is honest transparency); accuracy is None until something is
    decided — never a fake 0%. Pending/expired are excluded from the denominator."""
    stats: list[AlgorithmStats] = []
    for algorithm in ALGORITHMS:
        rows = [p for p in predictions if p.algorithm == algorithm]
        correct = sum(1 for p in rows if p.status == "correct")
        incorrect = sum(1 for p in rows if p.status == "incorrect")
        decided = correct + incorrect
        stats.append(
            AlgorithmStats(
                algorithm=algorithm,
                algorithm_name=ALGORITHM_NAMES[algorithm],
                total=len(rows),
                correct=correct,
                incorrect=incorrect,
                pending=sum(1 for p in rows if p.status == "pending"),
                expired=sum(1 for p in rows if p.status == "expired"),
                accuracy_pct=(
                    money(Decimal(correct) / Decimal(decided) * 100) if decided else None
                ),
            )
        )
    return stats


# --- Cycle (evaluate pending rows, then generate today's) ---------------------------


async def run_prediction_cycle(
    session: AsyncSession, yahoo
) -> tuple[int, int, int, list[str]]:
    """One full pass: evaluate/expire pending rows, then log new predictions.

    Returns (created, evaluated, expired, warnings). Raises
    PredictionsDataUnavailableError only when portfolio tickers exist and
    every Yahoo fetch failed.
    """
    pending = (
        (await session.execute(select(Prediction).where(Prediction.status == "pending")))
        .scalars()
        .all()
    )
    positions = (await session.execute(select(Position))).scalars().all()
    portfolio_tickers = sorted({p.ticker for p in positions})
    all_tickers = sorted({p.ticker for p in pending} | set(portfolio_tickers))

    warnings: list[str] = []
    candles, rate_limited = await fetch_daily_closes_cached(yahoo, all_tickers, warnings)
    if portfolio_tickers and not any(t in candles for t in portfolio_tickers):
        raise PredictionsDataUnavailableError(rate_limited=rate_limited)

    today = today_ny()

    evaluated = expired = 0
    for prediction in pending:
        series = candles.get(prediction.ticker)
        result = evaluate_prediction(prediction, series) if series else None
        if result is not None:
            outcome, eval_candle = result
            eval_close = money(eval_candle.close)
            prediction.status = outcome
            prediction.evaluation_date = eval_candle.date
            prediction.price_at_evaluation = eval_close
            prediction.actual_return_pct = pct_distance(
                eval_close, prediction.price_at_prediction
            )
            evaluated += 1
        elif is_expired(prediction, today):
            prediction.status = "expired"
            expired += 1

    created = 0
    for ticker in portfolio_tickers:
        series = candles.get(ticker)
        if not series:
            continue  # fetch failure already recorded a warning
        # Yahoo closes carry float32 artifacts — normalize to cents once.
        closes = [money(c.close) for c in series]
        prediction_date = series[-1].date
        for algorithm, predict in ALGORITHMS.items():
            direction = predict(closes)
            if direction is None:
                continue
            exists = await session.scalar(
                select(Prediction.id).where(
                    Prediction.ticker == ticker,
                    Prediction.algorithm == algorithm,
                    Prediction.prediction_date == prediction_date,
                )
            )
            if exists is not None:
                continue  # rerun the same candle day — clean no-op
            session.add(
                Prediction(
                    ticker=ticker,
                    algorithm=algorithm,
                    prediction_date=prediction_date,
                    predicted_direction=direction,
                    price_at_prediction=closes[-1],
                    horizon_days=HORIZON_TRADING_DAYS,
                    status="pending",
                )
            )
            created += 1

    await session.commit()
    return created, evaluated, expired, warnings


# --- APScheduler entry point ----------------------------------------------------


async def run_predictions_job() -> None:
    try:
        async with async_session_factory() as session:
            created, evaluated, expired, _ = await run_prediction_cycle(
                session, get_yahoo_client()
            )
        logger.info(
            "Prediction cycle done: %d created, %d evaluated, %d expired",
            created, evaluated, expired,
        )
    except Exception:
        logger.exception("Prediction cycle job failed")
