from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.protect import RiskLevel

RiskHorizon = Literal["short", "medium", "long"]
LossTolerance = Literal["sell", "hold", "buy_more"]
CapitalShare = Literal["large", "moderate", "small"]
InvestorProfile = Literal["conservative", "balanced", "aggressive"]


class RiskProfileIn(BaseModel):
    horizon: RiskHorizon
    loss_tolerance: LossTolerance
    capital_share: CapitalShare


class RiskProfileOut(BaseModel):
    horizon: RiskHorizon
    loss_tolerance: LossTolerance
    capital_share: CapitalShare
    score: int  # 3-9
    profile: InvestorProfile
    # From the latest cached Protect report; None when no report exists yet.
    protect_risk_level: RiskLevel | None
    # None when there is no Protect level to compare against.
    mismatch: bool | None
    mismatch_detail: str | None  # code-generated Turkish, only when mismatch is True
    updated_at: datetime | None
    disclaimer: str
