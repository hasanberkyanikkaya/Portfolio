from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import DailyReport
from app.schemas.market_pulse import MarketPulseContent, MarketPulseOut
from app.services.claude_client import (
    ClaudeClient,
    ClaudeError,
    ClaudeRateLimitError,
    get_claude_client,
)
from app.services.finnhub_client import FinnhubClient, get_finnhub_client
from app.services.market_pulse import (
    REPORT_MARKET_PULSE,
    MarketPulseDataUnavailableError,
    generate_market_pulse,
)
from app.services.yahoo_client import YahooClient, get_yahoo_client

router = APIRouter(prefix="/market-pulse", tags=["market-pulse"])


def _to_out(report: DailyReport) -> MarketPulseOut:
    return MarketPulseOut(
        report_date=report.report_date,
        content=MarketPulseContent.model_validate_json(report.content),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("", response_model=MarketPulseOut)
async def latest_market_pulse(db: AsyncSession = Depends(get_db)) -> MarketPulseOut:
    """Latest cached Market Pulse report. DB only — never calls Finnhub/Yahoo/Claude."""
    result = await db.execute(
        select(DailyReport)
        .where(DailyReport.report_type == REPORT_MARKET_PULSE)
        .order_by(DailyReport.report_date.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No Market Pulse report has been generated yet. "
            "Use POST /market-pulse/refresh to create one.",
        )
    return _to_out(report)


@router.post("/refresh", response_model=MarketPulseOut)
async def refresh_market_pulse(
    db: AsyncSession = Depends(get_db),
    finnhub: FinnhubClient = Depends(get_finnhub_client),
    yahoo: YahooClient = Depends(get_yahoo_client),
    claude: ClaudeClient = Depends(get_claude_client),
) -> MarketPulseOut:
    """Regenerate today's Market Pulse even if already cached.

    Partial data-source failures become `warnings` inside the content; only a
    total data blackout or a Claude failure maps to an HTTP error.
    """
    try:
        report = await generate_market_pulse(db, finnhub, yahoo, claude, force=True)
    except MarketPulseDataUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="No market data available right now — try again later.",
        )
    except ClaudeRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Anthropic rate limit reached — try again in a minute.",
        )
    except ClaudeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not generate the Market Pulse report right now: {exc}",
        )
    return _to_out(report)
