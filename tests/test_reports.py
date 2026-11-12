"""Tests for the daily-report generation and /reports endpoints (Phase 3)."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import DailyReport
from app.services.claude_client import ClaudeUnavailableError
from app.services.finnhub_client import FinnhubAuthError
from app.services.reports import generate_premarket_report


async def _count_reports(session_factory) -> int:
    async with session_factory() as session:
        return (await session.execute(select(func.count(DailyReport.id)))).scalar_one()


async def test_latest_returns_404_when_no_report_exists(client):
    response = await client.get("/reports/latest", params={"type": "premarket"})
    assert response.status_code == 404


async def test_refresh_then_latest_roundtrip(client, fake_claude):
    refresh = await client.post("/reports/refresh", json={"report_type": "premarket"})
    assert refresh.status_code == 200
    assert len(refresh.json()["reports"]) == 1

    latest = await client.get("/reports/latest", params={"type": "premarket"})
    assert latest.status_code == 200
    body = latest.json()
    assert body["report_type"] == "premarket"
    assert body["content"]["text"] == "Fake report text"
    assert fake_claude.calls == 1


async def test_refresh_twice_updates_single_row(client, fake_claude, session_factory):
    first = await client.post("/reports/refresh", json={"report_type": "premarket"})
    second = await client.post("/reports/refresh", json={"report_type": "premarket"})
    assert first.status_code == second.status_code == 200

    assert await _count_reports(session_factory) == 1
    assert fake_claude.calls == 2  # force=True regenerates
    assert second.json()["reports"][0]["updated_at"] is not None


async def test_refresh_both_returns_two_reports(client):
    response = await client.post("/reports/refresh", json={"report_type": "both"})
    assert response.status_code == 200
    types = {r["report_type"] for r in response.json()["reports"]}
    assert types == {"premarket", "close"}


async def test_scheduler_path_returns_cached_report(
    session_factory, fake_finnhub, fake_claude
):
    """force=False (the scheduler's mode) must not re-call Claude on the same day."""
    async with session_factory() as session:
        first = await generate_premarket_report(session, fake_finnhub, fake_claude)
        second = await generate_premarket_report(session, fake_finnhub, fake_claude)
    assert fake_claude.calls == 1
    assert first.id == second.id


async def test_calendar_403_degrades_to_warning(client, fake_finnhub):
    """Free-tier Finnhub: calendar endpoints 403 -> warning, report still generated."""
    fake_finnhub.calendar_error = FinnhubAuthError("Finnhub rejected the API key")
    response = await client.post("/reports/refresh", json={"report_type": "premarket"})
    assert response.status_code == 200
    warnings = response.json()["reports"][0]["content"]["warnings"]
    assert "economic_calendar_unavailable" in warnings


async def test_claude_failure_returns_503_and_writes_nothing(
    client, fake_claude, session_factory
):
    fake_claude.raise_on_call = ClaudeUnavailableError("Anthropic did not respond")
    response = await client.post("/reports/refresh", json={"report_type": "premarket"})
    assert response.status_code == 503
    assert await _count_reports(session_factory) == 0


async def test_duplicate_type_and_date_violates_constraint(session_factory):
    async with session_factory() as session:
        session.add(
            DailyReport(report_type="premarket", report_date=date(2026, 7, 8), content="{}")
        )
        await session.commit()
        session.add(
            DailyReport(report_type="premarket", report_date=date(2026, 7, 8), content="{}")
        )
        with pytest.raises(IntegrityError):
            await session.commit()
