from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

SetupRuleId = Literal["rsi_oversold_ma50", "ma200_reclaim", "low_rsi_divergence"]


class SetupItem(BaseModel):
    ticker: str
    rule_id: SetupRuleId
    rule_name: str  # Turkish display name (RULE_NAMES in services/setups.py)
    close: Decimal
    as_of: date  # date of the last Yahoo candle
    entry_zone_low: Decimal
    entry_zone_high: Decimal
    stop_loss: Decimal
    # Supporting numbers — per-rule relevance, None when not applicable.
    rsi_14: Decimal | None
    ma50: Decimal | None
    ma200: Decimal | None
    low_52w: Decimal | None
    swing_low_20: Decimal | None
    rationale: str  # code-generated Turkish, deterministic — Claude only rephrases


class SetupsData(BaseModel):
    positions_scanned: int  # unique tickers with usable close data
    setups: list[SetupItem]  # empty list is a first-class, valid result


class SetupsContent(BaseModel):
    """Parsed form of DailyReport.content for report_type="setups"."""

    text: str
    model: str
    generated_at: datetime
    warnings: list[str] = []
    data: SetupsData


class SetupsOut(BaseModel):
    report_date: date
    content: SetupsContent
    created_at: datetime
    updated_at: datetime | None
