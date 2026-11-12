from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

RiskLevel = Literal["low", "medium", "high"]
RiskFlagId = Literal[
    "position_concentration",
    "sector_concentration",
    "low_diversification",
    "unknown_sectors",
]
MacroEventType = Literal["FOMC", "CPI", "NFP", "other"]


class PositionWeight(BaseModel):
    ticker: str
    sector: str  # "Unknown" when the Finnhub profile is unavailable
    value: Decimal  # market value; cost basis when the quote failed
    weight_pct: Decimal
    weight_basis: Literal["market", "cost"]


class SectorWeight(BaseModel):
    sector: str
    weight_pct: Decimal
    tickers: list[str]


class RiskFlag(BaseModel):
    flag_id: RiskFlagId
    detail: str  # code-generated Turkish, numbers included
    tickers: list[str] = []


class MacroEvent(BaseModel):
    date: date
    event_type: MacroEventType
    title: str
    approximate: bool  # True for the static CPI estimates
    source: Literal["static", "finnhub"]
    sensitive_sectors: list[str] = []  # portfolio sectors matched by keyword
    affected_tickers: list[str] = []


class ProtectData(BaseModel):
    position_count: int  # unique tickers
    total_value: Decimal | None  # None only when the portfolio is empty
    risk_score: int  # 0-100, rule-based; Claude only explains it
    risk_level: RiskLevel
    positions: list[PositionWeight]  # sorted by weight desc
    sectors: list[SectorWeight]  # sorted by weight desc
    flags: list[RiskFlag]
    macro_events: list[MacroEvent]  # next 7 days, sorted by date


class ProtectContent(BaseModel):
    """Parsed form of DailyReport.content for report_type="protect"."""

    text: str
    model: str
    generated_at: datetime
    warnings: list[str] = []
    data: ProtectData


class ProtectOut(BaseModel):
    report_date: date
    content: ProtectContent
    created_at: datetime
    updated_at: datetime | None
