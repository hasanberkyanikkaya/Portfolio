from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import DailyReport
from app.schemas.report import (
    ReportContent,
    ReportOut,
    ReportRefreshRequest,
    ReportRefreshResponse,
    ReportType,
)
from app.services.claude_client import (
    ClaudeClient,
    ClaudeError,
    ClaudeRateLimitError,
    get_claude_client,
)
from app.services.finnhub_client import FinnhubClient, get_finnhub_client
from app.services.reports import generate_close_report, generate_premarket_report

router = APIRouter(prefix="/reports", tags=["reports"])


def _to_out(report: DailyReport) -> ReportOut:
    return ReportOut(
        report_type=report.report_type,
        report_date=report.report_date,
        content=ReportContent.model_validate_json(report.content),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("/latest", response_model=ReportOut)
async def latest_report(
    report_type: ReportType = Query(alias="type"),
    db: AsyncSession = Depends(get_db),
) -> ReportOut:
    """Latest cached report of the given type. DB only — never calls Claude."""
    result = await db.execute(
        select(DailyReport)
        .where(DailyReport.report_type == report_type)
        .order_by(DailyReport.report_date.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"No {report_type} report has been generated yet. "
            "Use POST /reports/refresh to create one.",
        )
    return _to_out(report)


@router.post("/refresh", response_model=ReportRefreshResponse)
async def refresh_reports(
    payload: ReportRefreshRequest,
    db: AsyncSession = Depends(get_db),
    finnhub: FinnhubClient = Depends(get_finnhub_client),
    claude: ClaudeClient = Depends(get_claude_client),
) -> ReportRefreshResponse:
    """Manual fallback: regenerate today's report(s) even if already cached.

    Finnhub data failures never surface here — they become `warnings` inside
    the report content. Only Claude failures map to HTTP errors.
    """
    generators = {
        "premarket": generate_premarket_report,
        "close": generate_close_report,
    }
    types = list(generators) if payload.report_type == "both" else [payload.report_type]

    reports: list[ReportOut] = []
    for report_type in types:
        try:
            report = await generators[report_type](db, finnhub, claude, force=True)
        except ClaudeRateLimitError:
            raise HTTPException(
                status_code=429,
                detail="Anthropic rate limit reached — try again in a minute.",
            )
        except ClaudeError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Could not generate the {report_type} report right now: {exc}",
            )
        reports.append(_to_out(report))
    return ReportRefreshResponse(reports=reports)
