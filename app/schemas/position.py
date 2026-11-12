from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PositionCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=10, examples=["AAPL"])
    quantity: Decimal = Field(gt=0, examples=[10])
    purchase_price: Decimal = Field(gt=0, examples=[150.25])
    purchase_date: date | None = Field(
        default=None, description="Defaults to today (America/New_York) if omitted."
    )

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or not all(ch.isalnum() or ch in ".-" for ch in value):
            raise ValueError("ticker may only contain letters, digits, '.' or '-'")
        return value


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    quantity: Decimal
    purchase_price: Decimal
    purchase_date: date
    created_at: datetime


class PositionWithPnL(PositionResponse):
    cost_basis: Decimal
    # These are None when Finnhub could not deliver a price (see price_status).
    current_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: Decimal | None
    price_status: Literal["ok", "unavailable"]


class PortfolioResponse(BaseModel):
    positions: list[PositionWithPnL]
    total_cost_basis: Decimal
    # Totals below only cover positions whose price could be fetched;
    # they are None when no position has a live price.
    total_market_value: Decimal | None
    total_unrealized_pnl: Decimal | None


class PositionCloseRequest(BaseModel):
    sale_price: Decimal = Field(gt=0, examples=[180.50])
    sale_date: date | None = Field(
        default=None, description="Defaults to today (America/New_York) if omitted."
    )


class RealizedTradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    quantity: Decimal
    purchase_price: Decimal
    sale_price: Decimal
    sale_date: date
    realized_pnl: Decimal
    created_at: datetime


class RealizedTradesResponse(BaseModel):
    trades: list[RealizedTradeResponse]
    total_realized_pnl: Decimal
