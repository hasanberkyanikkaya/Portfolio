from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

RspSpySignal = Literal["broad_participation", "megacap_concentration", "neutral"]


class SectorPerformance(BaseModel):
    symbol: str
    name: str
    daily_change_pct: Decimal | None  # Finnhub quote (dp)
    weekly_change_pct: Decimal | None  # Yahoo closes, 5 trading days back


class RspSpyComparison(BaseModel):
    rsp_daily_pct: Decimal | None
    spy_daily_pct: Decimal | None
    rsp_weekly_pct: Decimal | None
    spy_weekly_pct: Decimal | None
    daily_gap_pct: Decimal | None  # RSP - SPY
    weekly_gap_pct: Decimal | None
    signal: RspSpySignal  # rule-based in code; Claude only explains it


class MaPositioning(BaseModel):
    symbol: str
    index: str  # "S&P 500" / "Nasdaq 100"
    close: Decimal
    as_of: date  # date of the last Yahoo candle
    ma50: Decimal
    ma200: Decimal
    above_ma50: bool
    above_ma200: bool
    pct_from_ma50: Decimal
    pct_from_ma200: Decimal


class MarketPulseData(BaseModel):
    sectors: list[SectorPerformance]
    rsp_spy: RspSpyComparison | None  # None when both RSP and SPY data failed
    ma_positioning: list[MaPositioning]  # may be empty on data gaps


class MarketPulseContent(BaseModel):
    """Parsed form of DailyReport.content for report_type="market_pulse"."""

    text: str
    model: str
    generated_at: datetime
    warnings: list[str] = []
    data: MarketPulseData


class MarketPulseOut(BaseModel):
    report_date: date
    content: MarketPulseContent
    created_at: datetime
    updated_at: datetime | None
