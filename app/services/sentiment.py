"""Sentiment & Volatility report (Phase 5): a composite fear & greed score.

CNN publishes no official Fear & Greed API, so this is our own composite.
All data comes from Yahoo daily closes (Finnhub free tier has no VIX, no
candles, no highs/lows). All math is Decimal via pnl.money (2 dp,
ROUND_HALF_UP); Claude only narrates the precomputed numbers and label.

METHODOLOGY (tunable constants are module-level; 0 = extreme fear, 100 =
extreme greed; every component yields a 0-100 sub-score and is independently
degradable):

1. VIX vs its historical average (fear gauge, inverted)
   avg_252    = mean of the last 252 ^VIX closes (trailing 1-year mean —
                self-adapting to volatility regimes, unlike a fixed band)
   pct_vs_avg = (latest - avg_252) / avg_252 * 100
   score      = clamp(50 - pct_vs_avg * VIX_SENSITIVITY, 0, 100)
   -> VIX at its 1y mean = 50; 50% above the mean = 0; 50% below = 100.

2. Momentum: SPY vs its 125-day simple moving average
   pct_from_ma125 = (close - ma125) / ma125 * 100
   score          = clamp(50 + pct_from_ma125 * (50 / MOMENTUM_FULL_SCALE_PCT), 0, 100)
   -> at the MA = 50; +-MOMENTUM_FULL_SCALE_PCT (8%) spans the full range.

3. Breadth: new 52-week highs vs lows across a fixed 30-stock NASDAQ basket
   Accepted approximation: yahoo_client parses closes only, so "52-week
   high/low" means the CLOSING extreme of the trailing 252 sessions (including
   today), with a NEAR_EXTREME_PCT (1%) tolerance so the signal isn't
   degenerate:
     new high: latest >= max(window) * (1 - NEAR_EXTREME_PCT)
     new low:  latest <= min(window) * (1 + NEAR_EXTREME_PCT)
     both true (near-flat stock) -> counts as neither.
   Stocks with a failed fetch or < 252 closes are excluded from the universe;
   if the eligible universe drops below MIN_BREADTH_UNIVERSE the component is
   dropped entirely (a tiny sample is noise, not signal).
   net_ratio = (highs - lows) / universe * 100   (-100..100)
   score     = clamp(50 + net_ratio / 2, 0, 100)

4. Composite: equal-weight mean of the AVAILABLE sub-scores (implicit
   reweighting when a component is missing; `components_used` records the
   basis). All three missing -> SentimentDataUnavailableError, nothing is
   written and Claude is never called. Label thresholds (classify_sentiment):
   < 25 extreme_fear, < 45 fear, <= 55 neutral, <= 75 greed, else extreme_greed.

Yahoo etiquette: fetches are sequential (see yahoo_client docstring), ordered
^VIX -> SPY -> basket so the two highest-value components are secured first;
a 429 aborts the remaining basket fetches, and basket fetches are spaced by
BASKET_FETCH_DELAY_SECONDS (~8 s total, once a day).
"""

import asyncio
import logging
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.timeutils import today_ny
from app.models import DailyReport
from app.schemas.sentiment import (
    BreadthComponent,
    MomentumComponent,
    SentimentData,
    SentimentLabel,
    VixComponent,
)
from app.services.claude_client import get_claude_client
from app.services.market_pulse import pct_distance, sma
from app.services.pnl import money
from app.services.reports import _generate, _get_existing
from app.services.yahoo_client import (
    Candle,
    YahooError,
    YahooRateLimitError,
    get_yahoo_client,
)

logger = logging.getLogger(__name__)

REPORT_SENTIMENT = "sentiment"

VIX_SYMBOL = "^VIX"
MOMENTUM_SYMBOL = "SPY"

# Fixed basket of large-cap NASDAQ names for the highs/lows breadth component.
# Editorial list — revisit occasionally (delistings, index changes).
SENTIMENT_BASKET = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "COST", "NFLX",
    "AMD", "PEP", "ADBE", "CSCO", "QCOM", "INTC", "TXN", "AMAT", "INTU", "CMCSA",
    "HON", "AMGN", "BKNG", "SBUX", "GILD", "MU", "LRCX", "PANW", "MDLZ", "ADP",
]

# --- Tunables (see the module docstring for what each one does) ------------------
VIX_AVG_WINDOW = 252
MOMENTUM_MA_WINDOW = 125
HIGH_LOW_WINDOW = 252
VIX_SENSITIVITY = Decimal("1")  # score points per % deviation from the VIX mean
MOMENTUM_FULL_SCALE_PCT = Decimal("8")  # +-8% from MA125 spans the full 0-100
NEAR_EXTREME_PCT = Decimal("0.01")  # "near a 52w extreme" tolerance (1%)
MIN_BREADTH_UNIVERSE = 15
BASKET_FETCH_DELAY_SECONDS = 0.25


class SentimentDataUnavailableError(Exception):
    """All three components failed (Yahoo fully down). No report is generated —
    Claude must not be asked to comment on an empty payload."""


# --- Score math (pure, unit-testable) ---------------------------------------------


def clamp_score(value: Decimal) -> Decimal:
    return money(min(max(value, Decimal("0")), Decimal("100")))


def vix_score(pct_vs_avg: Decimal) -> Decimal:
    """Higher VIX than its mean -> more fear -> lower score."""
    return clamp_score(Decimal("50") - pct_vs_avg * VIX_SENSITIVITY)


def momentum_score(pct_from_ma: Decimal) -> Decimal:
    return clamp_score(
        Decimal("50") + pct_from_ma * (Decimal("50") / MOMENTUM_FULL_SCALE_PCT)
    )


def classify_high_low(closes: list[Decimal]) -> Literal["high", "low", "neither"]:
    """Closing 52-week high/low with the NEAR_EXTREME_PCT tolerance.
    Caller guarantees len(closes) >= HIGH_LOW_WINDOW."""
    window = closes[-HIGH_LOW_WINDOW:]
    latest = window[-1]
    is_high = latest >= max(window) * (Decimal("1") - NEAR_EXTREME_PCT)
    is_low = latest <= min(window) * (Decimal("1") + NEAR_EXTREME_PCT)
    if is_high and is_low:  # near-flat series — contradictory reading
        return "neither"
    if is_high:
        return "high"
    if is_low:
        return "low"
    return "neither"


def breadth_score(net_ratio_pct: Decimal) -> Decimal:
    return clamp_score(Decimal("50") + net_ratio_pct / 2)


def composite_score(scores: list[Decimal]) -> Decimal:
    """Equal-weight mean of the available sub-scores. Caller checks non-empty."""
    return money(sum(scores) / len(scores))


def classify_sentiment(score: Decimal) -> SentimentLabel:
    if score < 25:
        return "extreme_fear"
    if score < 45:
        return "fear"
    if score <= 55:
        return "neutral"
    if score <= 75:
        return "greed"
    return "extreme_greed"


# --- Data fetching -----------------------------------------------------------------


async def _fetch_closes(yahoo, warnings: list[str]) -> dict[str, list[Candle]]:
    """Sequential on purpose (Yahoo dislikes bursts). ^VIX and SPY first so the
    two highest-value components are secured before the long basket run; a 429
    mid-basket aborts the rest instead of hammering a rate-limiting host."""
    candles: dict[str, list[Candle]] = {}
    for symbol in (VIX_SYMBOL, MOMENTUM_SYMBOL):
        try:
            candles[symbol] = await yahoo.get_daily_closes(symbol)
        except YahooError:
            warnings.append(f"candles_unavailable:{symbol}")

    for i, symbol in enumerate(SENTIMENT_BASKET):
        if i > 0:
            await asyncio.sleep(BASKET_FETCH_DELAY_SECONDS)
        try:
            candles[symbol] = await yahoo.get_daily_closes(symbol)
        except YahooRateLimitError:
            warnings.append(f"candles_unavailable:{symbol}")
            warnings.append("breadth_aborted_rate_limit")
            break
        except YahooError:
            warnings.append(f"candles_unavailable:{symbol}")
    return candles


# --- Payload building ----------------------------------------------------------------


def _build_vix(candles: dict[str, list[Candle]], warnings: list[str]) -> VixComponent | None:
    series = candles.get(VIX_SYMBOL)
    if not series:
        return None  # fetch failure already warned as candles_unavailable:^VIX
    closes = [c.close for c in series]
    if len(closes) < VIX_AVG_WINDOW:
        warnings.append(f"vix_insufficient_history:{VIX_SYMBOL}")
        return None
    latest = money(closes[-1])
    avg = sma(closes, VIX_AVG_WINDOW)
    pct_vs_avg = pct_distance(latest, avg)
    return VixComponent(
        latest_close=latest,
        as_of=series[-1].date,
        avg_252=avg,
        pct_vs_avg=pct_vs_avg,
        score=vix_score(pct_vs_avg),
    )


def _build_momentum(
    candles: dict[str, list[Candle]], warnings: list[str]
) -> MomentumComponent | None:
    series = candles.get(MOMENTUM_SYMBOL)
    if not series:
        return None
    closes = [c.close for c in series]
    if len(closes) < MOMENTUM_MA_WINDOW:
        warnings.append(f"momentum_insufficient_history:{MOMENTUM_SYMBOL}")
        return None
    close = money(closes[-1])
    ma125 = sma(closes, MOMENTUM_MA_WINDOW)
    pct_from_ma = pct_distance(close, ma125)
    return MomentumComponent(
        spy_close=close,
        as_of=series[-1].date,
        ma125=ma125,
        pct_from_ma125=pct_from_ma,
        score=momentum_score(pct_from_ma),
    )


def _build_breadth(
    candles: dict[str, list[Candle]], warnings: list[str]
) -> BreadthComponent | None:
    highs = lows = universe = 0
    for symbol in SENTIMENT_BASKET:
        series = candles.get(symbol)
        if not series:
            continue  # fetch failure already warned per symbol
        closes = [c.close for c in series]
        if len(closes) < HIGH_LOW_WINDOW:
            warnings.append(f"breadth_insufficient_history:{symbol}")
            continue
        universe += 1
        verdict = classify_high_low(closes)
        if verdict == "high":
            highs += 1
        elif verdict == "low":
            lows += 1
    if universe < MIN_BREADTH_UNIVERSE:
        warnings.append("breadth_universe_too_small")
        return None
    net_ratio = money(Decimal(highs - lows) / universe * 100)
    return BreadthComponent(
        universe_size=universe,
        basket_size=len(SENTIMENT_BASKET),
        new_highs=highs,
        new_lows=lows,
        net_ratio_pct=net_ratio,
        score=breadth_score(net_ratio),
    )


def _build_data(
    candles: dict[str, list[Candle]], warnings: list[str]
) -> SentimentData | None:
    vix = _build_vix(candles, warnings)
    momentum = _build_momentum(candles, warnings)
    breadth = _build_breadth(candles, warnings)

    scores = [c.score for c in (vix, momentum, breadth) if c is not None]
    if not scores:
        return None
    score = composite_score(scores)
    return SentimentData(
        score=score,
        label=classify_sentiment(score),
        components_used=len(scores),
        vix=vix,
        momentum=momentum,
        breadth=breadth,
    )


# --- Generation -----------------------------------------------------------------


async def generate_sentiment(
    session: AsyncSession,
    yahoo,
    claude,
    *,
    report_date: date | None = None,
    force: bool = False,
) -> DailyReport:
    report_date = report_date or today_ny()
    existing = await _get_existing(session, REPORT_SENTIMENT, report_date)
    if existing is not None and not force:
        return existing

    warnings: list[str] = []
    candles = await _fetch_closes(yahoo, warnings)
    data = _build_data(candles, warnings)
    if data is None:
        raise SentimentDataUnavailableError(
            "No sentiment component data available from Yahoo Finance"
        )

    # The prompt payload and the stored "data" section are the identical dict —
    # what the frontend renders is exactly what Claude commented on.
    payload = data.model_dump()
    return await _generate(
        session,
        claude,
        REPORT_SENTIMENT,
        report_date,
        payload,
        warnings,
        extra_content={"data": payload},
    )


# --- APScheduler entry point ----------------------------------------------------


async def run_sentiment_job() -> None:
    try:
        async with async_session_factory() as session:
            report = await generate_sentiment(
                session, get_yahoo_client(), get_claude_client()
            )
        logger.info("Sentiment report ready for %s", report.report_date)
    except Exception:
        logger.exception("Sentiment report job failed")
