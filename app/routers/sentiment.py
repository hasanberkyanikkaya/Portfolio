from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import DailyReport
from app.schemas.sentiment import SentimentContent, SentimentOut
from app.services.claude_client import (
    ClaudeClient,
    ClaudeError,
    ClaudeRateLimitError,
    get_claude_client,
)
from app.services.sentiment import (
    REPORT_SENTIMENT,
    SentimentDataUnavailableError,
    generate_sentiment,
)
from app.services.yahoo_client import YahooClient, get_yahoo_client

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


def _to_out(report: DailyReport) -> SentimentOut:
    return SentimentOut(
        report_date=report.report_date,
        content=SentimentContent.model_validate_json(report.content),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("", response_model=SentimentOut)
async def latest_sentiment(db: AsyncSession = Depends(get_db)) -> SentimentOut:
    """Latest cached Sentiment report. DB only — never calls Yahoo/Claude."""
    result = await db.execute(
        select(DailyReport)
        .where(DailyReport.report_type == REPORT_SENTIMENT)
        .order_by(DailyReport.report_date.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No Sentiment report has been generated yet. "
            "Use POST /sentiment/refresh to create one.",
        )
    return _to_out(report)


@router.post("/refresh", response_model=SentimentOut)
async def refresh_sentiment(
    db: AsyncSession = Depends(get_db),
    yahoo: YahooClient = Depends(get_yahoo_client),
    claude: ClaudeClient = Depends(get_claude_client),
) -> SentimentOut:
    """Regenerate today's Sentiment report even if already cached.

    Partial component failures become `warnings` inside the content; only a
    total data blackout or a Claude failure maps to an HTTP error.
    """
    try:
        report = await generate_sentiment(db, yahoo, claude, force=True)
    except SentimentDataUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="No sentiment data available right now — try again later.",
        )
    except ClaudeRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Anthropic rate limit reached — try again in a minute.",
        )
    except ClaudeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not generate the Sentiment report right now: {exc}",
        )
    return _to_out(report)
