from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

ReportType = Literal["premarket", "close"]


class ReportContent(BaseModel):
    """Parsed form of DailyReport.content (stored as a JSON string)."""

    text: str
    model: str
    generated_at: datetime
    warnings: list[str] = []


class ReportOut(BaseModel):
    report_type: ReportType
    report_date: date
    content: ReportContent
    created_at: datetime
    updated_at: datetime | None


class ReportRefreshRequest(BaseModel):
    report_type: Literal["premarket", "close", "both"] = "both"


class ReportRefreshResponse(BaseModel):
    reports: list[ReportOut]
