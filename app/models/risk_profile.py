from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RiskProfile(Base):
    """The user's risk-profile questionnaire result (single-user: one row, upserted).

    Answer values are English slugs validated by the Pydantic Literal schema;
    `score` (3-9) and `profile` (conservative | balanced | aggressive) are
    computed by services/risk_profile.py at submit time.
    """

    __tablename__ = "risk_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    horizon: Mapped[str] = mapped_column(String(8))  # short | medium | long
    loss_tolerance: Mapped[str] = mapped_column(String(8))  # sell | hold | buy_more
    capital_share: Mapped[str] = mapped_column(String(8))  # large | moderate | small
    score: Mapped[int] = mapped_column(Integer)
    profile: Mapped[str] = mapped_column(String(16))  # conservative | balanced | aggressive
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
