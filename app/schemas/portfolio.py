from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

TechnicalLabel = Literal["strong", "weak", "neutral"]


class StockTechnical(BaseModel):
    ticker: str
    data_status: Literal["ok", "unavailable"]  # "unavailable" = Yahoo fetch failed
    close: Decimal | None
    as_of: date | None  # date of the last Yahoo candle
    high_52w: Decimal | None  # closing extreme of the trailing 252 sessions
    low_52w: Decimal | None
    pct_from_high_52w: Decimal | None  # (close - high) / high * 100, <= 0
    pct_from_low_52w: Decimal | None  # (close - low) / low * 100, >= 0
    ma50: Decimal | None
    ma200: Decimal | None
    above_ma50: bool | None
    above_ma200: bool | None
    pct_from_ma50: Decimal | None
    pct_from_ma200: Decimal | None
    earnings_this_week: bool | None  # None = earnings calendar unavailable
    earnings_date: date | None
    label: TechnicalLabel | None  # rule-based in code; None when inputs missing


class PortfolioTechnicalResponse(BaseModel):
    as_of_date: date
    stocks: list[StockTechnical]  # one per unique portfolio ticker, sorted
    warnings: list[str]


class NewsItem(BaseModel):
    headline: str
    source: str | None
    url: str | None
    summary: str | None
    published_at: datetime  # tz-aware (America/New_York)


class TickerNewsResponse(BaseModel):
    ticker: str
    from_date: date
    to_date: date
    items: list[NewsItem]  # newest first, capped at MAX_NEWS_ITEMS
