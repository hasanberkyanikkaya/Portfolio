import json
from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import DailyReport, RiskProfile
from app.schemas.risk_profile import RiskProfileIn
from app.services.risk_profile import classify_profile, is_mismatch, score_profile

ANSWERS_CONSERVATIVE = {"horizon": "short", "loss_tolerance": "sell", "capital_share": "large"}
ANSWERS_BALANCED = {"horizon": "medium", "loss_tolerance": "hold", "capital_share": "moderate"}
ANSWERS_AGGRESSIVE = {"horizon": "long", "loss_tolerance": "buy_more", "capital_share": "small"}


# --- Pure rules -------------------------------------------------------------------


def test_score_bounds():
    assert score_profile(RiskProfileIn(**ANSWERS_CONSERVATIVE)) == 3
    assert score_profile(RiskProfileIn(**ANSWERS_BALANCED)) == 6
    assert score_profile(RiskProfileIn(**ANSWERS_AGGRESSIVE)) == 9


@pytest.mark.parametrize(
    "score,expected",
    [(3, "conservative"), (4, "conservative"), (5, "balanced"),
     (7, "balanced"), (8, "aggressive"), (9, "aggressive")],
)
def test_classify_profile_boundaries(score, expected):
    assert classify_profile(score) == expected


@pytest.mark.parametrize(
    "profile,risk_level,expected",
    [
        ("conservative", "low", False),
        ("conservative", "medium", True),
        ("conservative", "high", True),
        ("balanced", "low", False),
        ("balanced", "medium", False),
        ("balanced", "high", True),
        ("aggressive", "low", False),
        ("aggressive", "medium", False),
        ("aggressive", "high", False),
    ],
)
def test_mismatch_matrix(profile, risk_level, expected):
    assert is_mismatch(profile, risk_level) is expected


# --- Endpoints --------------------------------------------------------------------


async def seed_protect_report(session_factory, risk_level="high"):
    content = json.dumps(
        {
            "text": "t", "model": "m", "generated_at": "2026-07-10T21:05:00+00:00",
            "warnings": [], "data": {"risk_level": risk_level},
        }
    )
    async with session_factory() as session:
        session.add(
            DailyReport(
                report_type="protect", report_date=date(2026, 7, 10), content=content
            )
        )
        await session.commit()


async def test_get_404_before_first_submit(client):
    response = await client.get("/risk-profile")
    assert response.status_code == 404


async def test_submit_and_roundtrip(client):
    response = await client.post("/risk-profile", json=ANSWERS_AGGRESSIVE)
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 9
    assert body["profile"] == "aggressive"
    assert body["protect_risk_level"] is None  # no Protect report yet
    assert body["mismatch"] is None
    assert body["mismatch_detail"] is None
    assert "istatistiksel" in body["disclaimer"]

    get_response = await client.get("/risk-profile")
    assert get_response.status_code == 200
    assert get_response.json()["profile"] == "aggressive"


async def test_resubmit_overwrites_single_row(client, session_factory):
    await client.post("/risk-profile", json=ANSWERS_AGGRESSIVE)
    response = await client.post("/risk-profile", json=ANSWERS_CONSERVATIVE)
    assert response.json()["profile"] == "conservative"

    async with session_factory() as session:
        count = (await session.execute(select(func.count(RiskProfile.id)))).scalar_one()
    assert count == 1


async def test_mismatch_against_seeded_protect_report(client, session_factory):
    await seed_protect_report(session_factory, risk_level="high")
    response = await client.post("/risk-profile", json=ANSWERS_CONSERVATIVE)
    body = response.json()
    assert body["protect_risk_level"] == "high"
    assert body["mismatch"] is True
    assert "temkinli" in body["mismatch_detail"]
    assert "yüksek" in body["mismatch_detail"]


async def test_no_mismatch_when_tolerated(client, session_factory):
    await seed_protect_report(session_factory, risk_level="low")
    response = await client.post("/risk-profile", json=ANSWERS_CONSERVATIVE)
    body = response.json()
    assert body["mismatch"] is False
    assert body["mismatch_detail"] is None


async def test_unparsable_protect_report_degrades(client, session_factory):
    async with session_factory() as session:
        session.add(
            DailyReport(
                report_type="protect", report_date=date(2026, 7, 10), content="not json"
            )
        )
        await session.commit()
    response = await client.post("/risk-profile", json=ANSWERS_BALANCED)
    assert response.status_code == 200
    assert response.json()["protect_risk_level"] is None
    assert response.json()["mismatch"] is None


async def test_invalid_choice_422(client):
    response = await client.post(
        "/risk-profile",
        json={"horizon": "forever", "loss_tolerance": "hold", "capital_share": "small"},
    )
    assert response.status_code == 422
