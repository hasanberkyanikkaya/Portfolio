from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Prediction(Base):
    """One rule-based direction prediction per (ticker, algorithm, prediction_date).

    `prediction_date` is the date of the last Yahoo candle the algorithm saw
    (not "today") so evaluation indexes align with candle dates and holiday
    reruns dedupe naturally. `status` lifecycle: pending -> correct/incorrect
    (evaluated against the close `horizon_days` trading days later) or
    expired (unevaluable for 30+ calendar days). Plain strings, no DB enums —
    same precedent as daily_reports.report_type.
    """

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "algorithm", "prediction_date", name="uq_predictions_ticker_algo_date"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    algorithm: Mapped[str] = mapped_column(String(32))  # trend_ma | rsi_reversion | swing_breakout
    prediction_date: Mapped[date] = mapped_column(Date)
    predicted_direction: Mapped[str] = mapped_column(String(8))  # up | down
    price_at_prediction: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    horizon_days: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(16), index=True, default="pending"
    )  # pending | correct | incorrect | expired
    evaluation_date: Mapped[date | None] = mapped_column(Date)
    price_at_evaluation: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    actual_return_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
