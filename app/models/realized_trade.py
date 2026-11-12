from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RealizedTrade(Base):
    __tablename__ = "realized_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 6))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    sale_price: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    sale_date: Mapped[date] = mapped_column(Date)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
