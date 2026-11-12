from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyReport(Base):
    """One Claude-generated market report per (report_type, report_date).

    `content` holds a JSON string: {"text", "model", "generated_at", "warnings"}.
    Kept as Text (not a JSON column) so it works identically on PostgreSQL and
    the aiosqlite test database.
    """

    __tablename__ = "daily_reports"
    __table_args__ = (
        UniqueConstraint("report_type", "report_date", name="uq_daily_reports_type_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[str] = mapped_column(String(16), index=True)  # premarket | close | market_pulse
    report_date: Mapped[date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
