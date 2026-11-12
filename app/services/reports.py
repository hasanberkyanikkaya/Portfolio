"""Daily report generation (Phase 3).

Single code path used by BOTH the APScheduler jobs and POST /reports/refresh:
build a data payload from Finnhub, render a prompt template, ask Claude for the
commentary, and upsert the result into daily_reports.

Caching rule (CLAUDE.md): the same day's report is never re-requested from
Claude — with force=False an existing (type, date) row is returned untouched.
The refresh endpoint passes force=True to regenerate in place.

Data gaps never fail generation: every Finnhub fetch is wrapped, and a failed
section becomes None in the payload plus an entry in `warnings` (on the free
tier the calendar endpoints return 403 -> FinnhubAuthError, which lands here).
"""

import asyncio
import json
import logging
import string
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.timeutils import today_ny
from app.models import DailyReport, Position
from app.services.claude_client import get_claude_client
from app.services.finnhub_client import (
    INDEX_PROXIES,
    FinnhubError,
    Quote,
    get_finnhub_client,
)

logger = logging.getLogger(__name__)

REPORT_PREMARKET = "premarket"
REPORT_CLOSE = "close"

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache
def load_prompt(name: str) -> string.Template:
    """Load app/prompts/<name>.txt once. string.Template (not str.format) so the
    editable templates can contain literal JSON braces."""
    return string.Template((PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8"))


def _quote_dict(quote: Quote | None) -> dict | None:
    if quote is None:
        return None
    return {
        "current_price": quote.current_price,
        "change": quote.change,
        "percent_change": quote.percent_change,
        "previous_close": quote.previous_close,
    }


async def _fetch_index_quotes(finnhub, warnings: list[str]) -> dict | None:
    try:
        quotes = await finnhub.get_index_quotes()
    except FinnhubError:
        warnings.append("index_quotes_unavailable")
        return None
    section = {}
    for symbol, quote in quotes.items():
        if quote is None:
            warnings.append(f"index_quote_unavailable:{symbol}")
        section[symbol] = {"index": INDEX_PROXIES[symbol], **(_quote_dict(quote) or {})}
    return section


async def _fetch_economic_calendar(
    finnhub, from_date: date, to_date: date, warnings: list[str]
) -> list[dict] | None:
    try:
        return await finnhub.get_economic_calendar(from_date, to_date)
    except FinnhubError:
        warnings.append("economic_calendar_unavailable")
        return None


async def _fetch_earnings_calendar(
    finnhub, from_date: date, to_date: date, warnings: list[str]
) -> list[dict] | None:
    try:
        return await finnhub.get_earnings_calendar(from_date, to_date)
    except FinnhubError:
        warnings.append("earnings_calendar_unavailable")
        return None


async def _fetch_portfolio_moves(
    session: AsyncSession, finnhub, warnings: list[str]
) -> list[dict]:
    """Today's move for each open position (quote data only — no P&L math here;
    Claude must never compute, and pnl.py owns the real numbers)."""
    positions = (await session.execute(select(Position))).scalars().all()
    tickers = sorted({p.ticker for p in positions})
    if not tickers:
        return []
    results = await asyncio.gather(
        *(finnhub.get_quote(t) for t in tickers), return_exceptions=True
    )
    moves: list[dict] = []
    for ticker, result in zip(tickers, results):
        if isinstance(result, Quote):
            moves.append({"ticker": ticker, **_quote_dict(result)})
        else:
            warnings.append(f"quote_unavailable:{ticker}")
            moves.append({"ticker": ticker, "quote": None})
    return moves


async def _get_existing(
    session: AsyncSession, report_type: str, report_date: date
) -> DailyReport | None:
    result = await session.execute(
        select(DailyReport).where(
            DailyReport.report_type == report_type,
            DailyReport.report_date == report_date,
        )
    )
    return result.scalar_one_or_none()


async def _upsert_report(
    session: AsyncSession, report_type: str, report_date: date, content: str
) -> DailyReport:
    """Portable select-then-update (tests run sqlite, so no pg ON CONFLICT)."""
    report = await _get_existing(session, report_type, report_date)
    if report is None:
        report = DailyReport(
            report_type=report_type, report_date=report_date, content=content
        )
        session.add(report)
    else:
        report.content = content
    await session.commit()
    await session.refresh(report)
    return report


async def _generate(
    session: AsyncSession,
    claude,
    report_type: str,
    report_date: date,
    payload: dict,
    warnings: list[str],
    extra_content: dict | None = None,
) -> DailyReport:
    """`extra_content` lets a report type store structured data alongside the
    Claude text (Market Pulse keeps its numeric sections under "data")."""
    payload_json = json.dumps(payload, default=str, ensure_ascii=False, indent=2)
    user_content = load_prompt(report_type).substitute(
        report_date=report_date.isoformat(), payload_json=payload_json
    )
    text = await claude.generate(
        system=load_prompt("system").template, user_content=user_content
    )
    content = json.dumps(
        {
            "text": text,
            "model": get_settings().anthropic_model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "warnings": warnings,
            **(extra_content or {}),
        },
        default=str,
        ensure_ascii=False,
    )
    return await _upsert_report(session, report_type, report_date, content)


async def generate_premarket_report(
    session: AsyncSession,
    finnhub,
    claude,
    *,
    report_date: date | None = None,
    force: bool = False,
) -> DailyReport:
    report_date = report_date or today_ny()
    existing = await _get_existing(session, REPORT_PREMARKET, report_date)
    if existing is not None and not force:
        return existing

    warnings: list[str] = []
    payload = {
        "index_proxies": await _fetch_index_quotes(finnhub, warnings),
        "economic_calendar_today": await _fetch_economic_calendar(
            finnhub, report_date, report_date, warnings
        ),
    }
    return await _generate(session, claude, REPORT_PREMARKET, report_date, payload, warnings)


async def generate_close_report(
    session: AsyncSession,
    finnhub,
    claude,
    *,
    report_date: date | None = None,
    force: bool = False,
) -> DailyReport:
    report_date = report_date or today_ny()
    existing = await _get_existing(session, REPORT_CLOSE, report_date)
    if existing is not None and not force:
        return existing

    warnings: list[str] = []
    # +1..+3 days so the Friday close report reaches Monday's agenda.
    upcoming_from = report_date + timedelta(days=1)
    upcoming_to = report_date + timedelta(days=3)
    payload = {
        "index_proxies": await _fetch_index_quotes(finnhub, warnings),
        "portfolio_day_moves": await _fetch_portfolio_moves(session, finnhub, warnings),
        "upcoming_economic_calendar": await _fetch_economic_calendar(
            finnhub, upcoming_from, upcoming_to, warnings
        ),
        "upcoming_earnings_calendar": await _fetch_earnings_calendar(
            finnhub, upcoming_from, upcoming_to, warnings
        ),
    }
    return await _generate(session, claude, REPORT_CLOSE, report_date, payload, warnings)


# --- APScheduler entry points -------------------------------------------------
# No DI inside scheduler jobs: they open their own session and use the shared
# process-global clients. A failed job must never crash the event loop.


async def run_premarket_job() -> None:
    try:
        async with async_session_factory() as session:
            report = await generate_premarket_report(
                session, get_finnhub_client(), get_claude_client()
            )
        logger.info("Premarket report ready for %s", report.report_date)
    except Exception:
        logger.exception("Premarket report job failed")


async def run_close_job() -> None:
    try:
        async with async_session_factory() as session:
            report = await generate_close_report(
                session, get_finnhub_client(), get_claude_client()
            )
        logger.info("Close report ready for %s", report.report_date)
    except Exception:
        logger.exception("Close report job failed")
