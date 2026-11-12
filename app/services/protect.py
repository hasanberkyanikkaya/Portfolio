"""Protect — portfolio risk report (Phase 7).

Concentration analysis + a rule-based risk level + a "which holdings are
sensitive to this week's macro events" mapping. Claude only summarizes the
precomputed payload in Turkish — the score, level, flags and weights are
never recomputed or second-guessed.

WEIGHTS: one Finnhub quote per unique ticker (concurrent, same pattern as
GET /positions); a ticker's value = sum of money(price * qty) across its
position rows (duplicate rows aggregate). A failed quote falls back to the
ticker's COST BASIS (weight_basis="cost", warning
`weight_uses_cost_basis:{ticker}`) so weights still sum to ~100 instead of
silently under-reporting concentration. Sectors come from Finnhub
/stock/profile2 `finnhubIndustry` (free tier), memoized in-process per ticker
(sectors don't change intra-day); a failed profile degrades the ticker to
sector "Unknown" (warning `sector_unavailable:{ticker}`).

FLAGS (rule-based, thresholds are module constants):
- position_concentration: any ticker weight   > POSITION_FLAG_PCT (20%)
- sector_concentration:   any KNOWN sector    > SECTOR_FLAG_PCT (40%)
- low_diversification:    unique tickers      < MIN_COMFORT_POSITIONS (5)
- unknown_sectors:        "Unknown" weight   >= UNKNOWN_FLAG_PCT (50%)

RISK SCORE (0-100, sum of four point components; first matching row of each
table wins — tables below):
- top position weight >= 40/30/20/15 %  ->  40/30/20/10 points
- top KNOWN sector    >= 60/40/30 %     ->  30/20/10 points
- position count      <= 2 / <= 4      ->  20/10 points
- Unknown sector      >= 50 %           ->  10 points
classify_risk: score < 30 -> "low", 30-60 -> "medium", > 60 -> "high".
Sanity anchors: a single-stock portfolio scores 90 (high); a balanced
8-name multi-sector book scores ~0 (low).

EMPTY PORTFOLIO: score 0 / "low" / empty lists — still a valid report (the
macro events are portfolio-independent); Claude is called and narrates it.
ProtectDataUnavailableError is defensive only: the cost-basis fallback means
a portfolio with rows always has a positive total value.

MACRO EVENTS: services/macro_calendar.py (static editorial 2026 FOMC/CPI/NFP
dates + a best-effort Finnhub merge that 403s into a warning on the free
tier). Each event gets `sensitive_sectors` = portfolio sectors whose
finnhubIndustry contains one of the event type's keywords, and
`affected_tickers` = the tickers in those sectors.
"""

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.timeutils import today_ny
from app.models import DailyReport, Position
from app.schemas.protect import (
    MacroEvent,
    PositionWeight,
    ProtectData,
    RiskFlag,
    RiskLevel,
    SectorWeight,
)
from app.services.claude_client import get_claude_client
from app.services.finnhub_client import FinnhubError, Quote, get_finnhub_client
from app.services.macro_calendar import (
    EVENT_SECTOR_SENSITIVITY,
    MACRO_LOOKAHEAD_DAYS,
    finnhub_events,
    static_events,
)
from app.services.pnl import money
from app.services.reports import _generate, _get_existing

logger = logging.getLogger(__name__)

REPORT_PROTECT = "protect"
UNKNOWN_SECTOR = "Unknown"

# --- Thresholds / point tables (see the module docstring) -------------------------
POSITION_FLAG_PCT = Decimal("20")
SECTOR_FLAG_PCT = Decimal("40")
MIN_COMFORT_POSITIONS = 5
UNKNOWN_FLAG_PCT = Decimal("50")

# (minimum weight %, points) — first matching row wins.
TOP_POSITION_POINTS = [(Decimal("40"), 40), (Decimal("30"), 30), (Decimal("20"), 20), (Decimal("15"), 10)]
TOP_SECTOR_POINTS = [(Decimal("60"), 30), (Decimal("40"), 20), (Decimal("30"), 10)]
# (maximum position count, points) — first matching row wins.
DIVERSIFICATION_POINTS = [(2, 20), (4, 10)]
UNKNOWN_SECTOR_POINTS = 10


class ProtectDataUnavailableError(Exception):
    """Positions exist but no value could be computed (defensive — the
    cost-basis fallback makes this practically unreachable)."""


# In-process memo: ticker -> finnhubIndustry (successes only).
_sector_cache: dict[str, str] = {}


def clear_protect_cache() -> None:
    _sector_cache.clear()


# --- Risk math (pure, unit-testable) ------------------------------------------------


def classify_risk(score: int) -> RiskLevel:
    if score < 30:
        return "low"
    if score <= 60:
        return "medium"
    return "high"


def build_position_weights(
    rows: list[Position],
    quotes: dict[str, Quote],
    sectors: dict[str, str],
    warnings: list[str],
) -> tuple[list[PositionWeight], Decimal | None]:
    """Aggregate position rows into per-ticker weights (duplicates merge).

    Returns (weights sorted desc, total value) — (list, None) when empty.
    """
    values: dict[str, Decimal] = {}
    basis: dict[str, str] = {}
    for row in rows:
        quote = quotes.get(row.ticker)
        if quote is not None:
            value = money(quote.current_price * row.quantity)
        else:
            value = money(row.purchase_price * row.quantity)
        # Quotes are per-ticker, so every row of a ticker shares one basis.
        basis[row.ticker] = "market" if quote is not None else "cost"
        values[row.ticker] = values.get(row.ticker, Decimal("0")) + value

    for ticker in sorted(values):
        if basis[ticker] == "cost":
            warnings.append(f"weight_uses_cost_basis:{ticker}")

    total = sum(values.values(), Decimal("0"))
    if not values:
        return [], None
    if total <= 0:
        raise ProtectDataUnavailableError("Portfolio total value is not positive")

    weights = [
        PositionWeight(
            ticker=ticker,
            sector=sectors.get(ticker, UNKNOWN_SECTOR),
            value=money(value),
            weight_pct=money(value / total * 100),
            weight_basis=basis[ticker],
        )
        for ticker, value in values.items()
    ]
    weights.sort(key=lambda w: w.weight_pct, reverse=True)
    return weights, money(total)


def build_sector_weights(positions: list[PositionWeight]) -> list[SectorWeight]:
    by_sector: dict[str, list[PositionWeight]] = {}
    for position in positions:
        by_sector.setdefault(position.sector, []).append(position)
    sectors = [
        SectorWeight(
            sector=sector,
            weight_pct=money(sum(p.weight_pct for p in members)),
            tickers=sorted(p.ticker for p in members),
        )
        for sector, members in by_sector.items()
    ]
    sectors.sort(key=lambda s: s.weight_pct, reverse=True)
    return sectors


def _table_points(value, table) -> int:
    for threshold, points in table:
        if value >= threshold:
            return points
    return 0


def compute_risk(
    positions: list[PositionWeight], sectors: list[SectorWeight]
) -> tuple[int, RiskLevel, list[RiskFlag]]:
    if not positions:
        return 0, "low", []

    known_sectors = [s for s in sectors if s.sector != UNKNOWN_SECTOR]
    unknown_weight = next(
        (s.weight_pct for s in sectors if s.sector == UNKNOWN_SECTOR), Decimal("0")
    )
    top_position = positions[0]  # already sorted desc
    top_sector = known_sectors[0] if known_sectors else None

    score = _table_points(top_position.weight_pct, TOP_POSITION_POINTS)
    if top_sector is not None:
        score += _table_points(top_sector.weight_pct, TOP_SECTOR_POINTS)
    for max_count, points in DIVERSIFICATION_POINTS:
        if len(positions) <= max_count:
            score += points
            break
    if unknown_weight >= UNKNOWN_FLAG_PCT:
        score += UNKNOWN_SECTOR_POINTS

    flags: list[RiskFlag] = []
    heavy = [p for p in positions if p.weight_pct > POSITION_FLAG_PCT]
    if heavy:
        listing = ", ".join(f"{p.ticker} %{p.weight_pct}" for p in heavy)
        flags.append(
            RiskFlag(
                flag_id="position_concentration",
                detail=f"Tek pozisyon ağırlığı %{POSITION_FLAG_PCT} eşiğini aşıyor: {listing}.",
                tickers=[p.ticker for p in heavy],
            )
        )
    heavy_sectors = [s for s in known_sectors if s.weight_pct > SECTOR_FLAG_PCT]
    if heavy_sectors:
        listing = ", ".join(f"{s.sector} %{s.weight_pct}" for s in heavy_sectors)
        flags.append(
            RiskFlag(
                flag_id="sector_concentration",
                detail=f"Sektör ağırlığı %{SECTOR_FLAG_PCT} eşiğini aşıyor: {listing}.",
                tickers=sorted(t for s in heavy_sectors for t in s.tickers),
            )
        )
    if len(positions) < MIN_COMFORT_POSITIONS:
        flags.append(
            RiskFlag(
                flag_id="low_diversification",
                detail=(
                    f"Portföyde yalnızca {len(positions)} pozisyon var "
                    f"(rahat çeşitlendirme eşiği: {MIN_COMFORT_POSITIONS})."
                ),
                tickers=[p.ticker for p in positions],
            )
        )
    if unknown_weight >= UNKNOWN_FLAG_PCT:
        unknown_tickers = [p.ticker for p in positions if p.sector == UNKNOWN_SECTOR]
        flags.append(
            RiskFlag(
                flag_id="unknown_sectors",
                detail=(
                    f"Portföyün %{unknown_weight} kadarının sektörü belirlenemedi — "
                    f"sektör riski değerlendirilemiyor."
                ),
                tickers=unknown_tickers,
            )
        )

    return score, classify_risk(score), flags


def match_sensitivity(
    event_type: str, sectors: list[SectorWeight]
) -> tuple[list[str], list[str]]:
    """Portfolio sectors (and their tickers) matching the event's keywords."""
    keywords = EVENT_SECTOR_SENSITIVITY.get(event_type, [])
    matched = [
        s
        for s in sectors
        if s.sector != UNKNOWN_SECTOR
        and any(keyword in s.sector.lower() for keyword in keywords)
    ]
    sensitive = [s.sector for s in matched]
    affected = sorted({t for s in matched for t in s.tickers})
    return sensitive, affected


# --- Data fetching --------------------------------------------------------------


async def _fetch_sectors(
    finnhub, tickers: list[str], warnings: list[str]
) -> dict[str, str]:
    missing = [t for t in tickers if t not in _sector_cache]
    results = await asyncio.gather(
        *(finnhub.get_company_profile(t) for t in missing), return_exceptions=True
    )
    for ticker, result in zip(missing, results):
        if isinstance(result, BaseException):
            if not isinstance(result, FinnhubError):
                raise result
            warnings.append(f"sector_unavailable:{ticker}")
            continue
        sector = (result.get("finnhubIndustry") or "").strip()
        if sector:
            _sector_cache[ticker] = sector
        else:
            warnings.append(f"sector_unavailable:{ticker}")
    return {t: _sector_cache[t] for t in tickers if t in _sector_cache}


# --- Generation -----------------------------------------------------------------


async def generate_protect(
    session: AsyncSession,
    finnhub,
    claude,
    *,
    report_date: date | None = None,
    force: bool = False,
) -> DailyReport:
    report_date = report_date or today_ny()
    existing = await _get_existing(session, REPORT_PROTECT, report_date)
    if existing is not None and not force:
        return existing

    rows = (await session.execute(select(Position).order_by(Position.id))).scalars().all()
    tickers = sorted({row.ticker for row in rows})

    warnings: list[str] = []
    quote_results = await asyncio.gather(
        *(finnhub.get_quote(t) for t in tickers), return_exceptions=True
    )
    quotes = {
        ticker: result
        for ticker, result in zip(tickers, quote_results)
        if isinstance(result, Quote)
    }
    sectors = await _fetch_sectors(finnhub, tickers, warnings)

    positions, total_value = build_position_weights(rows, quotes, sectors, warnings)
    sector_weights = build_sector_weights(positions)
    score, level, flags = compute_risk(positions, sector_weights)

    start = today_ny()
    end = start + timedelta(days=MACRO_LOOKAHEAD_DAYS)
    raw_events = static_events(start) + await finnhub_events(finnhub, start, end, warnings)
    events: list[MacroEvent] = []
    for event in sorted(raw_events, key=lambda e: e.date):
        sensitive, affected = match_sensitivity(event.event_type, sector_weights)
        events.append(
            event.model_copy(
                update={"sensitive_sectors": sensitive, "affected_tickers": affected}
            )
        )

    data = ProtectData(
        position_count=len(positions),
        total_value=total_value,
        risk_score=score,
        risk_level=level,
        positions=positions,
        sectors=sector_weights,
        flags=flags,
        macro_events=events,
    )

    # The prompt payload and the stored "data" section are the identical dict —
    # what the frontend renders is exactly what Claude commented on.
    payload = data.model_dump()
    return await _generate(
        session,
        claude,
        REPORT_PROTECT,
        report_date,
        payload,
        warnings,
        extra_content={"data": payload},
    )


# --- APScheduler entry point ----------------------------------------------------


async def run_protect_job() -> None:
    try:
        async with async_session_factory() as session:
            report = await generate_protect(
                session, get_finnhub_client(), get_claude_client()
            )
        logger.info("Protect report ready for %s", report.report_date)
    except Exception:
        logger.exception("Protect report job failed")
