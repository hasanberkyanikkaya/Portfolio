"""Market Pulse (Phase 4): sector rotation + technical positioning.

Data sources:
- Finnhub quotes  -> today's percent change for each sector ETF, RSP and SPY.
- Yahoo candles   -> weekly performance and the 50/200-day moving averages
  (Finnhub's /stock/candle is premium; Yahoo's chart API is free and keyless).

Reuses the Phase 3 pipeline from services/reports.py (_get_existing/_generate
-> daily_reports upsert) with report_type="market_pulse" — same caching rule,
same warnings-instead-of-failures degradation. All math is Decimal and lives
here; Claude only explains the precomputed numbers and the breadth label.
"""

import asyncio
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.timeutils import today_ny
from app.models import DailyReport
from app.schemas.market_pulse import (
    MaPositioning,
    MarketPulseData,
    RspSpyComparison,
    RspSpySignal,
    SectorPerformance,
)
from app.services.claude_client import get_claude_client
from app.services.finnhub_client import Quote, get_finnhub_client
from app.services.pnl import money
from app.services.reports import _generate, _get_existing
from app.services.yahoo_client import Candle, YahooError, get_yahoo_client

logger = logging.getLogger(__name__)

REPORT_MARKET_PULSE = "market_pulse"

SECTOR_ETFS: dict[str, str] = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "SMH": "Semiconductors",
    "XBI": "Biotech",
}

MA_SYMBOLS: dict[str, str] = {"SPY": "S&P 500", "QQQ": "Nasdaq 100"}

# RSP-SPY gap thresholds (percentage points) for the rule-based breadth signal.
DAILY_GAP_THRESHOLD = Decimal("0.25")
WEEKLY_GAP_THRESHOLD = Decimal("0.75")


class MarketPulseDataUnavailableError(Exception):
    """Every numeric section failed (Finnhub AND Yahoo down). No report is
    generated — Claude must not be asked to comment on an empty payload."""


# --- Decimal math ---------------------------------------------------------------


def sma(closes: list[Decimal], n: int) -> Decimal:
    """Simple moving average over the last n closes. Caller checks len >= n."""
    return money(sum(closes[-n:]) / n)


def pct_distance(close: Decimal, ma: Decimal) -> Decimal:
    return money((close - ma) / ma * 100)


def weekly_change(closes: list[Decimal]) -> Decimal | None:
    """Last close vs the close 5 trading days earlier (candle close-to-close;
    at 16:50 ET the last candle may be today's or yesterday's — `as_of` in the
    MA section records which)."""
    if len(closes) < 6:
        return None
    return money((closes[-1] - closes[-6]) / closes[-6] * 100)


def classify_rsp_spy(daily_gap: Decimal | None, weekly_gap: Decimal | None) -> RspSpySignal:
    """Rule-based read of the RSP-SPY gap (equal-weight minus cap-weight S&P).

    A positive gap breaching a threshold reads as broad participation, a
    negative one as a few mega-caps carrying the index; small or conflicting
    gaps are neutral. A missing gap never breaches.
    """
    positive = (daily_gap is not None and daily_gap >= DAILY_GAP_THRESHOLD) or (
        weekly_gap is not None and weekly_gap >= WEEKLY_GAP_THRESHOLD
    )
    negative = (daily_gap is not None and daily_gap <= -DAILY_GAP_THRESHOLD) or (
        weekly_gap is not None and weekly_gap <= -WEEKLY_GAP_THRESHOLD
    )
    if positive and not negative:
        return "broad_participation"
    if negative and not positive:
        return "megacap_concentration"
    return "neutral"


# --- Payload building -----------------------------------------------------------


async def _fetch_daily_changes(finnhub, warnings: list[str]) -> dict[str, Decimal | None]:
    """Today's percent change for each sector ETF plus RSP and SPY."""
    symbols = [*SECTOR_ETFS, "RSP", "SPY"]
    results = await asyncio.gather(
        *(finnhub.get_quote(s) for s in symbols), return_exceptions=True
    )
    changes: dict[str, Decimal | None] = {}
    for symbol, result in zip(symbols, results):
        if isinstance(result, Quote) and result.percent_change is not None:
            changes[symbol] = money(result.percent_change)
        else:
            prefix = (
                "sector_quote_unavailable"
                if symbol in SECTOR_ETFS
                else "rsp_spy_quote_unavailable"
            )
            warnings.append(f"{prefix}:{symbol}")
            changes[symbol] = None
    return changes


async def _fetch_candles(yahoo, warnings: list[str]) -> dict[str, list[Candle]]:
    """Sequential on purpose — Yahoo's unofficial API dislikes bursts (see
    yahoo_client docstring)."""
    candles: dict[str, list[Candle]] = {}
    for symbol in [*SECTOR_ETFS, "RSP", "SPY", "QQQ"]:
        try:
            candles[symbol] = await yahoo.get_daily_closes(symbol)
        except YahooError:
            warnings.append(f"candles_unavailable:{symbol}")
    return candles


def _build_data(
    daily: dict[str, Decimal | None],
    candles: dict[str, list[Candle]],
    warnings: list[str],
) -> MarketPulseData:
    sectors = [
        SectorPerformance(
            symbol=symbol,
            name=name,
            daily_change_pct=daily.get(symbol),
            weekly_change_pct=weekly_change([c.close for c in candles.get(symbol, [])]),
        )
        for symbol, name in SECTOR_ETFS.items()
    ]

    rsp_daily, spy_daily = daily.get("RSP"), daily.get("SPY")
    rsp_weekly = weekly_change([c.close for c in candles.get("RSP", [])])
    spy_weekly = weekly_change([c.close for c in candles.get("SPY", [])])
    daily_gap = (
        money(rsp_daily - spy_daily)
        if rsp_daily is not None and spy_daily is not None
        else None
    )
    weekly_gap = (
        money(rsp_weekly - spy_weekly)
        if rsp_weekly is not None and spy_weekly is not None
        else None
    )
    if daily_gap is None and weekly_gap is None:
        rsp_spy = None
        warnings.append("rsp_spy_unavailable")
    else:
        rsp_spy = RspSpyComparison(
            rsp_daily_pct=rsp_daily,
            spy_daily_pct=spy_daily,
            rsp_weekly_pct=rsp_weekly,
            spy_weekly_pct=spy_weekly,
            daily_gap_pct=daily_gap,
            weekly_gap_pct=weekly_gap,
            signal=classify_rsp_spy(daily_gap, weekly_gap),
        )

    ma_positioning: list[MaPositioning] = []
    for symbol, index_name in MA_SYMBOLS.items():
        series = candles.get(symbol)
        if not series:
            warnings.append(f"ma_unavailable:{symbol}")
            continue
        closes = [c.close for c in series]
        if len(closes) < 200:
            warnings.append(f"ma_insufficient_history:{symbol}")
            continue
        # Yahoo closes carry float32 artifacts (745.4000244140625) — store cents.
        close, ma50, ma200 = money(closes[-1]), sma(closes, 50), sma(closes, 200)
        ma_positioning.append(
            MaPositioning(
                symbol=symbol,
                index=index_name,
                close=close,
                as_of=series[-1].date,
                ma50=ma50,
                ma200=ma200,
                above_ma50=close > ma50,
                above_ma200=close > ma200,
                pct_from_ma50=pct_distance(close, ma50),
                pct_from_ma200=pct_distance(close, ma200),
            )
        )

    return MarketPulseData(sectors=sectors, rsp_spy=rsp_spy, ma_positioning=ma_positioning)


def _all_unavailable(data: MarketPulseData) -> bool:
    return (
        all(
            s.daily_change_pct is None and s.weekly_change_pct is None
            for s in data.sectors
        )
        and data.rsp_spy is None
        and not data.ma_positioning
    )


# --- Generation -----------------------------------------------------------------


async def generate_market_pulse(
    session: AsyncSession,
    finnhub,
    yahoo,
    claude,
    *,
    report_date: date | None = None,
    force: bool = False,
) -> DailyReport:
    report_date = report_date or today_ny()
    existing = await _get_existing(session, REPORT_MARKET_PULSE, report_date)
    if existing is not None and not force:
        return existing

    warnings: list[str] = []
    daily = await _fetch_daily_changes(finnhub, warnings)
    candles = await _fetch_candles(yahoo, warnings)
    data = _build_data(daily, candles, warnings)
    if _all_unavailable(data):
        raise MarketPulseDataUnavailableError(
            "No market data available from Finnhub or Yahoo Finance"
        )

    # The prompt payload and the stored "data" section are the identical dict —
    # what the frontend renders is exactly what Claude commented on.
    payload = data.model_dump()
    return await _generate(
        session,
        claude,
        REPORT_MARKET_PULSE,
        report_date,
        payload,
        warnings,
        extra_content={"data": payload},
    )


# --- APScheduler entry point ----------------------------------------------------


async def run_market_pulse_job() -> None:
    try:
        async with async_session_factory() as session:
            report = await generate_market_pulse(
                session, get_finnhub_client(), get_yahoo_client(), get_claude_client()
            )
        logger.info("Market Pulse report ready for %s", report.report_date)
    except Exception:
        logger.exception("Market Pulse report job failed")
