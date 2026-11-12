"""Risk profile — questionnaire scoring vs the portfolio's Protect risk level (Phase 8).

Three fixed-choice questions, each worth 1-3 points (higher = more risk
capacity); the sum (3-9) classifies the investor:

    horizon:        short=1  medium=2  long=3     (yatırım ufku)
    loss_tolerance: sell=1   hold=2    buy_more=3 (portföy %20 düşerse?)
    capital_share:  large=1  moderate=2 small=3   (paranın birikimdeki yeri)

    classify_profile: score <= 4 -> conservative, <= 7 -> balanced, else aggressive
    (same shape as protect.classify_risk).

MISMATCH RULE (is_mismatch): flag only when the PORTFOLIO's Protect risk level
exceeds what the profile tolerates — an aggressive investor holding a low-risk
book is not a problem. conservative flags medium+high, balanced flags high,
aggressive never flags. The comparison reads the latest cached Protect report
(report_type="protect") from daily_reports; no Protect report -> mismatch is
None ("henüz karşılaştırılamıyor"), never an error.

Single-user app: exactly one risk_profiles row, upserted on every submit.
Pure rule-based — no Claude, no external APIs.
"""

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyReport, RiskProfile
from app.schemas.protect import RiskLevel
from app.schemas.risk_profile import InvestorProfile, RiskProfileIn
from app.services.protect import REPORT_PROTECT

logger = logging.getLogger(__name__)

# Points per answer value (higher = more risk capacity).
ANSWER_POINTS: dict[str, dict[str, int]] = {
    "horizon": {"short": 1, "medium": 2, "long": 3},
    "loss_tolerance": {"sell": 1, "hold": 2, "buy_more": 3},
    "capital_share": {"large": 1, "moderate": 2, "small": 3},
}

CONSERVATIVE_MAX = 4
BALANCED_MAX = 7

PROFILE_NAMES_TR: dict[str, str] = {
    "conservative": "temkinli",
    "balanced": "dengeli",
    "aggressive": "agresif",
}

RISK_LEVEL_NAMES_TR: dict[str, str] = {
    "low": "düşük",
    "medium": "orta",
    "high": "yüksek",
}

# Protect risk levels each profile tolerates without a flag.
_TOLERATED: dict[str, set[str]] = {
    "conservative": {"low"},
    "balanced": {"low", "medium"},
    "aggressive": {"low", "medium", "high"},
}


# --- Pure rules (unit-testable) ----------------------------------------------------


def score_profile(answers: RiskProfileIn) -> int:
    return (
        ANSWER_POINTS["horizon"][answers.horizon]
        + ANSWER_POINTS["loss_tolerance"][answers.loss_tolerance]
        + ANSWER_POINTS["capital_share"][answers.capital_share]
    )


def classify_profile(score: int) -> InvestorProfile:
    if score <= CONSERVATIVE_MAX:
        return "conservative"
    if score <= BALANCED_MAX:
        return "balanced"
    return "aggressive"


def is_mismatch(profile: InvestorProfile, risk_level: RiskLevel) -> bool:
    return risk_level not in _TOLERATED[profile]


def mismatch_detail(profile: InvestorProfile, risk_level: RiskLevel) -> str:
    return (
        f"Profiliniz '{PROFILE_NAMES_TR[profile]}' ancak portföyün Protect risk "
        f"seviyesi '{RISK_LEVEL_NAMES_TR[risk_level]}' — portföy riski risk "
        f"profilinizin üzerinde. Pozisyon ve sektör yoğunlaşmasını gözden "
        f"geçirmek isteyebilirsiniz."
    )


# --- DB helpers ---------------------------------------------------------------------


async def get_profile_row(session: AsyncSession) -> RiskProfile | None:
    return (await session.execute(select(RiskProfile).limit(1))).scalar_one_or_none()


async def upsert_profile(session: AsyncSession, answers: RiskProfileIn) -> RiskProfile:
    score = score_profile(answers)
    profile = classify_profile(score)
    row = await get_profile_row(session)
    if row is None:
        row = RiskProfile(
            horizon=answers.horizon,
            loss_tolerance=answers.loss_tolerance,
            capital_share=answers.capital_share,
            score=score,
            profile=profile,
        )
        session.add(row)
    else:
        row.horizon = answers.horizon
        row.loss_tolerance = answers.loss_tolerance
        row.capital_share = answers.capital_share
        row.score = score
        row.profile = profile
    await session.commit()
    await session.refresh(row)
    return row


async def latest_protect_risk_level(session: AsyncSession) -> RiskLevel | None:
    """risk_level from the latest cached Protect report; None when there is no
    report or its content can't be parsed (a broken report never breaks this
    endpoint)."""
    result = await session.execute(
        select(DailyReport)
        .where(DailyReport.report_type == REPORT_PROTECT)
        .order_by(DailyReport.report_date.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if report is None:
        return None
    try:
        level = json.loads(report.content)["data"]["risk_level"]
    except (ValueError, KeyError, TypeError):
        logger.warning("Latest Protect report content is unparsable — skipping comparison")
        return None
    return level if level in RISK_LEVEL_NAMES_TR else None
