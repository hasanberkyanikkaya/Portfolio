from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

SentimentLabel = Literal["extreme_fear", "fear", "neutral", "greed", "extreme_greed"]


class VixComponent(BaseModel):
    latest_close: Decimal
    as_of: date  # date of the last Yahoo candle
    avg_252: Decimal  # trailing 1-year mean of VIX closes
    pct_vs_avg: Decimal  # latest vs the mean, in percent
    score: Decimal  # 0-100 sub-score (higher = greed)


class MomentumComponent(BaseModel):
    spy_close: Decimal
    as_of: date
    ma125: Decimal
    pct_from_ma125: Decimal
    score: Decimal


class BreadthComponent(BaseModel):
    universe_size: int  # eligible stocks (fetched with >= 252 closes)
    basket_size: int  # full SENTIMENT_BASKET size
    new_highs: int
    new_lows: int
    net_ratio_pct: Decimal  # (highs - lows) / universe * 100
    score: Decimal


class SentimentData(BaseModel):
    score: Decimal  # composite 0-100; rule-based, Claude only explains it
    label: SentimentLabel
    components_used: int  # how many of the three components had data
    vix: VixComponent | None
    momentum: MomentumComponent | None
    breadth: BreadthComponent | None


class SentimentContent(BaseModel):
    """Parsed form of DailyReport.content for report_type="sentiment"."""

    text: str
    model: str
    generated_at: datetime
    warnings: list[str] = []
    data: SentimentData


class SentimentOut(BaseModel):
    report_date: date
    content: SentimentContent
    created_at: datetime
    updated_at: datetime | None
