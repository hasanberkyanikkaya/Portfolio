from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import RiskProfile
from app.schemas.risk_profile import RiskProfileIn, RiskProfileOut
from app.services.disclaimers import STATISTICAL_DISCLAIMER
from app.services.risk_profile import (
    get_profile_row,
    is_mismatch,
    latest_protect_risk_level,
    mismatch_detail,
    upsert_profile,
)

router = APIRouter(prefix="/risk-profile", tags=["risk-profile"])


async def _to_out(row: RiskProfile, db: AsyncSession) -> RiskProfileOut:
    risk_level = await latest_protect_risk_level(db)
    mismatch = None if risk_level is None else is_mismatch(row.profile, risk_level)
    return RiskProfileOut(
        horizon=row.horizon,
        loss_tolerance=row.loss_tolerance,
        capital_share=row.capital_share,
        score=row.score,
        profile=row.profile,
        protect_risk_level=risk_level,
        mismatch=mismatch,
        mismatch_detail=mismatch_detail(row.profile, risk_level) if mismatch else None,
        updated_at=row.updated_at or row.created_at,
        disclaimer=STATISTICAL_DISCLAIMER,
    )


@router.get("", response_model=RiskProfileOut)
async def get_risk_profile(db: AsyncSession = Depends(get_db)) -> RiskProfileOut:
    """Current profile + comparison against the latest Protect risk level. DB only."""
    row = await get_profile_row(db)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No risk profile submitted yet. Use POST /risk-profile first.",
        )
    return await _to_out(row, db)


@router.post("", response_model=RiskProfileOut)
async def submit_risk_profile(
    answers: RiskProfileIn, db: AsyncSession = Depends(get_db)
) -> RiskProfileOut:
    """Submit (or re-submit) the questionnaire — single row, upserted."""
    row = await upsert_profile(db, answers)
    return await _to_out(row, db)
