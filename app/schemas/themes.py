from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

PriceStatus = Literal["ok", "unavailable"]


class Theme(BaseModel):
    slug: str
    name: str  # Turkish display name
    description: str  # Turkish, 1-2 sentences
    tickers: list[str]  # NASDAQ symbols, uppercase


class ThemeSummary(BaseModel):
    slug: str
    name: str
    description: str
    ticker_count: int


class ThemesListResponse(BaseModel):
    themes: list[ThemeSummary]
    disclaimer: str


class ThemeStock(BaseModel):
    ticker: str
    price: Decimal | None
    percent_change: Decimal | None  # daily %
    industry: str | None  # finnhubIndustry; None when the profile fetch failed
    price_status: PriceStatus


class ThemeDetailResponse(BaseModel):
    slug: str
    name: str
    description: str
    stocks: list[ThemeStock]
    warnings: list[str]
    disclaimer: str
