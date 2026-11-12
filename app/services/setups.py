"""Setups — rule-based opportunity scanning (Phase 7).

Scans every unique portfolio ticker's Yahoo daily closes (shared per-NY-day
memo cache with services/technical.py) against fixed, explicit rules. All
levels (entry zone, stop-loss) and the rationale text are computed by code;
Claude only narrates the payload in Turkish and never invents or adjusts a
number. An empty setups list is a first-class result — the rules only fire
when their conditions are actually met.

DATA CAVEAT: Yahoo gives daily CLOSES only (no intraday high/low, no volume),
so "swing low" and "52w low" are CLOSING extremes — the same approximation the
Sentiment breadth and technical modules already accept.

RULES (first match wins, priority S1 > S2 > S3 — max one setup per ticker so
the report stays focused):

S1 `rsi_oversold_ma50` — oversold pullback to MA50 support in an uptrend
   close > MA200 (long-term uptrend intact)
   AND RSI(14) <= RSI_OVERSOLD (35)
   AND |close vs MA50| <= MA50_PROXIMITY_PCT (3%)  ("testing MA50")
   entry zone = MA50 * (1 ± ENTRY_BAND_PCT (2%))
   stop       = 20-session swing low * (1 - STOP_BUFFER_PCT (1%))

S2 `ma200_reclaim` — fresh reclaim of the 200-day MA
   close > MA200 today, but not extended: close vs MA200 <= RECLAIM_MAX_EXTENSION_PCT (3%)
   AND, of the prior RECLAIM_LOOKBACK_SESSIONS (10) sessions (excluding today),
   at least RECLAIM_MIN_SESSIONS_BELOW (3) closed below their own same-day
   rolling MA200 (so the reclaim is recent, not ancient history)
   entry zone = [MA200, close]
   stop       = 20-session swing low * (1 - 1%)

S3 `low_rsi_divergence` — 52w-low retest with improving momentum
   close within NEAR_LOW_BAND_PCT (5%) ABOVE the 52w closing low (and above it)
   AND the 52w low is at least DIVERGENCE_MIN_SESSIONS_AGO (5) sessions old
   AND RSI(14) now >= RSI(14) at the low + DIVERGENCE_MIN_RSI_DELTA (5)
   AND RSI(14) now <= DIVERGENCE_RSI_MAX (50)  (divergence, not a breakout)
   entry zone = [52w low, close]
   stop       = 52w low * (1 - 1%)

GEOMETRY GUARD: a setup whose stop is not strictly below its entry_zone_low is
discarded silently (invalid risk geometry — can happen when the swing low sits
inside the entry band).

RSI: Wilder's smoothing (seed = simple mean of the first `period` deltas, then
avg = (prev * (period-1) + current) / period). Money-rounded 0-100; needs at
least period + 1 closes. All math is Decimal via pnl.money.

Degradation mirrors technical.py: a failed Yahoo fetch skips the ticker with a
`candles_unavailable:{ticker}` warning; a Yahoo 429 aborts the remaining
fetches; only when positions exist and EVERY fetch failed does generation
raise SetupsDataUnavailableError (rate_limited decides 429 vs 503). Claude is
ALWAYS called otherwise — the "no setups today is normal" narration is part of
the product, and every cached report carries a Turkish text.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.timeutils import today_ny
from app.models import DailyReport, Position
from app.schemas.setups import SetupItem, SetupsData
from app.services.claude_client import get_claude_client
from app.services.market_pulse import pct_distance, sma
from app.services.pnl import money
from app.services.reports import _generate, _get_existing
from app.services.sentiment import HIGH_LOW_WINDOW
from app.services.technical import fetch_daily_closes_cached
from app.services.yahoo_client import Candle, get_yahoo_client

logger = logging.getLogger(__name__)

REPORT_SETUPS = "setups"

# --- Tunables (see the module docstring for what each one does) ------------------
RSI_PERIOD = 14
RSI_OVERSOLD = Decimal("35")
MA50_PROXIMITY_PCT = Decimal("3")
ENTRY_BAND_PCT = Decimal("2")
SWING_LOOKBACK_SESSIONS = 20
STOP_BUFFER_PCT = Decimal("1")
RECLAIM_LOOKBACK_SESSIONS = 10
RECLAIM_MIN_SESSIONS_BELOW = 3
RECLAIM_MAX_EXTENSION_PCT = Decimal("3")
NEAR_LOW_BAND_PCT = Decimal("5")
DIVERGENCE_MIN_RSI_DELTA = Decimal("5")
DIVERGENCE_MIN_SESSIONS_AGO = 5
DIVERGENCE_RSI_MAX = Decimal("50")

RULE_NAMES: dict[str, str] = {
    "rsi_oversold_ma50": "MA50 destek testi (RSI aşırı satım)",
    "ma200_reclaim": "Taze MA200 geri kazanımı",
    "low_rsi_divergence": "52 hafta dibinde RSI uyumsuzluğu",
}


class SetupsDataUnavailableError(Exception):
    """Positions exist but every ticker's Yahoo fetch failed."""

    def __init__(self, rate_limited: bool) -> None:
        self.rate_limited = rate_limited
        super().__init__(
            "Yahoo rate limit hit before any ticker could be fetched"
            if rate_limited
            else "No historical data available for any portfolio ticker"
        )


# --- Indicator math (pure, unit-testable) -------------------------------------------


def rsi(closes: list[Decimal], period: int = RSI_PERIOD) -> Decimal | None:
    """Wilder RSI over the full series; None if fewer than period + 1 closes."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else Decimal("0") for d in deltas]
    losses = [-d if d < 0 else Decimal("0") for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return Decimal("100.00") if avg_gain > 0 else Decimal("50.00")
    rs = avg_gain / avg_loss
    return money(Decimal("100") - Decimal("100") / (1 + rs))


def swing_low(closes: list[Decimal]) -> Decimal:
    """Lowest CLOSE of the trailing SWING_LOOKBACK_SESSIONS sessions."""
    return money(min(closes[-SWING_LOOKBACK_SESSIONS:]))


def stop_from(reference_low: Decimal) -> Decimal:
    return money(reference_low * (1 - STOP_BUFFER_PCT / 100))


# --- Rule checks (each returns a SetupItem or None) ----------------------------------


def _check_rsi_oversold_ma50(
    ticker: str, closes: list[Decimal], as_of: date
) -> SetupItem | None:
    if len(closes) < 200:
        return None
    close = money(closes[-1])
    ma50 = sma(closes, 50)
    ma200 = sma(closes, 200)
    rsi_14 = rsi(closes)
    if rsi_14 is None or close <= ma200 or rsi_14 > RSI_OVERSOLD:
        return None
    if abs(pct_distance(close, ma50)) > MA50_PROXIMITY_PCT:
        return None
    low_20 = swing_low(closes)
    return SetupItem(
        ticker=ticker,
        rule_id="rsi_oversold_ma50",
        rule_name=RULE_NAMES["rsi_oversold_ma50"],
        close=close,
        as_of=as_of,
        entry_zone_low=money(ma50 * (1 - ENTRY_BAND_PCT / 100)),
        entry_zone_high=money(ma50 * (1 + ENTRY_BAND_PCT / 100)),
        stop_loss=stop_from(low_20),
        rsi_14=rsi_14,
        ma50=ma50,
        ma200=ma200,
        low_52w=None,
        swing_low_20=low_20,
        rationale=(
            f"RSI(14) {rsi_14} ile aşırı satım bölgesinde; fiyat ({close}$) "
            f"MA50'ye ({ma50}$) %{MA50_PROXIMITY_PCT} bandında yakın ve MA200 "
            f"({ma200}$) üzerinde — uzun vadeli yükseliş trendi korunuyor, "
            f"geri çekilme MA50 desteğini test ediyor olabilir."
        ),
    )


def _check_ma200_reclaim(
    ticker: str, closes: list[Decimal], as_of: date
) -> SetupItem | None:
    if len(closes) < 200 + RECLAIM_LOOKBACK_SESSIONS:
        return None
    close = money(closes[-1])
    ma200 = sma(closes, 200)
    if close <= ma200 or pct_distance(close, ma200) > RECLAIM_MAX_EXTENSION_PCT:
        return None
    # Of the prior N sessions (excluding today), how many closed below their
    # own same-day rolling MA200? A fresh reclaim needs a recent stay below.
    sessions_below = 0
    for offset in range(2, RECLAIM_LOOKBACK_SESSIONS + 2):
        history = closes[: len(closes) - offset + 1]
        if history[-1] < sma(history, 200):
            sessions_below += 1
    if sessions_below < RECLAIM_MIN_SESSIONS_BELOW:
        return None
    low_20 = swing_low(closes)
    rsi_14 = rsi(closes)
    return SetupItem(
        ticker=ticker,
        rule_id="ma200_reclaim",
        rule_name=RULE_NAMES["ma200_reclaim"],
        close=close,
        as_of=as_of,
        entry_zone_low=ma200,
        entry_zone_high=close,
        stop_loss=stop_from(low_20),
        rsi_14=rsi_14,
        ma50=sma(closes, 50),
        ma200=ma200,
        low_52w=None,
        swing_low_20=low_20,
        rationale=(
            f"Fiyat ({close}$) son {RECLAIM_LOOKBACK_SESSIONS} seansın en az "
            f"{RECLAIM_MIN_SESSIONS_BELOW} tanesinde MA200 altında kapandıktan "
            f"sonra MA200'ün ({ma200}$) üzerine yeni çıktı ve henüz %"
            f"{RECLAIM_MAX_EXTENSION_PCT} bandını aşmadı — taze bir geri "
            f"kazanım denemesi olabilir."
        ),
    )


def _check_low_rsi_divergence(
    ticker: str, closes: list[Decimal], as_of: date
) -> SetupItem | None:
    if len(closes) < HIGH_LOW_WINDOW:
        return None
    window = closes[-HIGH_LOW_WINDOW:]
    low_pos = min(range(len(window)), key=window.__getitem__)
    sessions_since_low = len(window) - 1 - low_pos
    if sessions_since_low < DIVERGENCE_MIN_SESSIONS_AGO:
        return None
    low_52w = money(window[low_pos])
    close = money(closes[-1])
    if close <= low_52w or close > money(low_52w * (1 + NEAR_LOW_BAND_PCT / 100)):
        return None
    low_idx = len(closes) - HIGH_LOW_WINDOW + low_pos
    rsi_now = rsi(closes)
    rsi_at_low = rsi(closes[: low_idx + 1])
    if rsi_now is None or rsi_at_low is None:
        return None
    if rsi_now < rsi_at_low + DIVERGENCE_MIN_RSI_DELTA or rsi_now > DIVERGENCE_RSI_MAX:
        return None
    return SetupItem(
        ticker=ticker,
        rule_id="low_rsi_divergence",
        rule_name=RULE_NAMES["low_rsi_divergence"],
        close=close,
        as_of=as_of,
        entry_zone_low=low_52w,
        entry_zone_high=close,
        stop_loss=stop_from(low_52w),
        rsi_14=rsi_now,
        ma50=sma(closes, 50) if len(closes) >= 50 else None,
        ma200=sma(closes, 200) if len(closes) >= 200 else None,
        low_52w=low_52w,
        swing_low_20=swing_low(closes),
        rationale=(
            f"Fiyat ({close}$) 52 haftalık kapanış dibinin ({low_52w}$) %"
            f"{NEAR_LOW_BAND_PCT} bandında seyrederken RSI(14) dip anındaki "
            f"{rsi_at_low} seviyesinden {rsi_now} seviyesine yükseldi — fiyat "
            f"dibi yeniden test ederken momentumun iyileşmesi pozitif "
            f"uyumsuzluk olarak okunabilir."
        ),
    )


_RULE_CHECKS = (
    _check_rsi_oversold_ma50,
    _check_ma200_reclaim,
    _check_low_rsi_divergence,
)


def detect_setup(ticker: str, series: list[Candle]) -> SetupItem | None:
    """First matching rule (S1 > S2 > S3) that also passes the geometry guard."""
    # Yahoo closes carry float32 artifacts — normalize to cents once, up front.
    closes = [money(c.close) for c in series]
    as_of = series[-1].date
    for check in _RULE_CHECKS:
        item = check(ticker, closes, as_of)
        if item is not None and item.stop_loss < item.entry_zone_low:
            return item
    return None


def build_setups_data(
    candles: dict[str, list[Candle]], tickers: list[str], warnings: list[str]
) -> SetupsData:
    if not tickers:
        warnings.append("empty_portfolio")
    setups = []
    for ticker in tickers:
        series = candles.get(ticker)
        if not series:
            continue  # fetch failure already recorded a warning
        item = detect_setup(ticker, series)
        if item is not None:
            setups.append(item)
    return SetupsData(positions_scanned=len(candles), setups=setups)


# --- Generation -----------------------------------------------------------------


async def generate_setups(
    session: AsyncSession,
    yahoo,
    claude,
    *,
    report_date: date | None = None,
    force: bool = False,
) -> DailyReport:
    report_date = report_date or today_ny()
    existing = await _get_existing(session, REPORT_SETUPS, report_date)
    if existing is not None and not force:
        return existing

    positions = (await session.execute(select(Position))).scalars().all()
    tickers = sorted({p.ticker for p in positions})

    warnings: list[str] = []
    candles, rate_limited = await fetch_daily_closes_cached(yahoo, tickers, warnings)
    if tickers and not candles:
        raise SetupsDataUnavailableError(rate_limited=rate_limited)

    data = build_setups_data(candles, tickers, warnings)

    # The prompt payload and the stored "data" section are the identical dict —
    # what the frontend renders is exactly what Claude commented on.
    payload = data.model_dump()
    return await _generate(
        session,
        claude,
        REPORT_SETUPS,
        report_date,
        payload,
        warnings,
        extra_content={"data": payload},
    )


# --- APScheduler entry point ----------------------------------------------------


async def run_setups_job() -> None:
    try:
        async with async_session_factory() as session:
            report = await generate_setups(
                session, get_yahoo_client(), get_claude_client()
            )
        logger.info("Setups report ready for %s", report.report_date)
    except Exception:
        logger.exception("Setups report job failed")
