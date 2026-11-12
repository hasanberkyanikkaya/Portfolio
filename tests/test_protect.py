from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import DailyReport, Position
from app.schemas.protect import PositionWeight, SectorWeight
from app.services.claude_client import ClaudeRateLimitError, ClaudeUnavailableError
from app.services.finnhub_client import FinnhubAuthError, Quote
from app.services.macro_calendar import first_friday, static_events
from app.services.protect import (
    build_position_weights,
    classify_risk,
    compute_risk,
    generate_protect,
    match_sensitivity,
)


async def create_position(client, ticker="AAPL", quantity="10", price="150.00"):
    response = await client.post(
        "/positions",
        json={"ticker": ticker, "quantity": quantity, "purchase_price": price},
    )
    assert response.status_code == 201
    return response


async def _count_reports(session_factory) -> int:
    async with session_factory() as session:
        return (await session.execute(select(func.count(DailyReport.id)))).scalar_one()


def _quote(price: str) -> Quote:
    return Quote(
        current_price=Decimal(price), change=None, percent_change=None, previous_close=None
    )


def _row(ticker: str, quantity: str, price: str) -> Position:
    return Position(
        ticker=ticker,
        quantity=Decimal(quantity),
        purchase_price=Decimal(price),
        purchase_date=date(2026, 1, 2),
    )


def _pw(ticker: str, weight: str, sector: str = "Technology") -> PositionWeight:
    return PositionWeight(
        ticker=ticker, sector=sector, value=Decimal("100"),
        weight_pct=Decimal(weight), weight_basis="market",
    )


# --- Weights (pure) -----------------------------------------------------------------


def test_weights_aggregate_duplicate_tickers():
    rows = [_row("AAPL", "10", "150"), _row("AAPL", "5", "180"), _row("MSFT", "10", "300")]
    quotes = {"AAPL": _quote("200"), "MSFT": _quote("400")}
    warnings: list[str] = []
    weights, total = build_position_weights(rows, quotes, {"AAPL": "Technology"}, warnings)

    assert total == Decimal("7000.00")  # (10+5)*200 + 10*400
    assert [w.ticker for w in weights] == ["MSFT", "AAPL"]  # sorted by weight desc
    aapl = next(w for w in weights if w.ticker == "AAPL")
    assert aapl.value == Decimal("3000.00")
    assert aapl.weight_pct == Decimal("42.86")
    assert aapl.sector == "Technology"
    msft = next(w for w in weights if w.ticker == "MSFT")
    assert msft.sector == "Unknown"
    assert warnings == []


def test_weights_cost_basis_fallback_on_failed_quote():
    rows = [_row("AAPL", "10", "150"), _row("MSFT", "10", "300")]
    quotes = {"AAPL": _quote("200")}  # MSFT quote failed
    warnings: list[str] = []
    weights, total = build_position_weights(rows, quotes, {}, warnings)

    msft = next(w for w in weights if w.ticker == "MSFT")
    assert msft.weight_basis == "cost"
    assert msft.value == Decimal("3000.00")  # 10 * purchase 300
    assert total == Decimal("5000.00")
    assert "weight_uses_cost_basis:MSFT" in warnings


def test_weights_empty_portfolio():
    weights, total = build_position_weights([], {}, {}, [])
    assert weights == [] and total is None


# --- Risk score / flags (pure) --------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "low"), (29, "low"), (30, "medium"), (60, "medium"), (61, "high"), (100, "high")],
)
def test_classify_risk_boundaries(score, expected):
    assert classify_risk(score) == expected


def test_single_stock_portfolio_is_high_risk():
    positions = [_pw("AAPL", "100.00")]
    sectors = [SectorWeight(sector="Technology", weight_pct=Decimal("100.00"), tickers=["AAPL"])]
    score, level, flags = compute_risk(positions, sectors)
    assert score == 90  # 40 (top position) + 30 (top sector) + 20 (<=2 positions)
    assert level == "high"
    assert {f.flag_id for f in flags} == {
        "position_concentration", "sector_concentration", "low_diversification",
    }


def test_balanced_book_is_low_risk():
    positions = [_pw(f"T{i}", "12.50", sector=f"Sector{i % 4}") for i in range(8)]
    sectors = [
        SectorWeight(sector=f"Sector{i}", weight_pct=Decimal("25.00"), tickers=[])
        for i in range(4)
    ]
    score, level, flags = compute_risk(positions, sectors)
    assert score == 0
    assert level == "low"
    assert flags == []


def test_position_flag_threshold_is_strict():
    sectors = [SectorWeight(sector="Technology", weight_pct=Decimal("100"), tickers=[])]
    at_threshold = [_pw("AAPL", "20.00")] + [_pw(f"T{i}", "16.00") for i in range(5)]
    _, _, flags = compute_risk(at_threshold, sectors)
    assert "position_concentration" not in {f.flag_id for f in flags}

    above = [_pw("AAPL", "20.01")] + [_pw(f"T{i}", "16.00") for i in range(5)]
    _, _, flags = compute_risk(above, sectors)
    assert "position_concentration" in {f.flag_id for f in flags}


def test_unknown_sectors_flag_and_points():
    positions = [
        _pw("AAA", "30.00", sector="Unknown"),
        _pw("BBB", "30.00", sector="Unknown"),
        _pw("CCC", "20.00", sector="Technology"),
        _pw("DDD", "10.00", sector="Retail"),
        _pw("EEE", "10.00", sector="Banks"),
    ]
    sectors = [
        SectorWeight(sector="Unknown", weight_pct=Decimal("60.00"), tickers=["AAA", "BBB"]),
        SectorWeight(sector="Technology", weight_pct=Decimal("20.00"), tickers=["CCC"]),
        SectorWeight(sector="Retail", weight_pct=Decimal("10.00"), tickers=["DDD"]),
        SectorWeight(sector="Banks", weight_pct=Decimal("10.00"), tickers=["EEE"]),
    ]
    score, _, flags = compute_risk(positions, sectors)
    # 30 (top position >= 30%) + 0 (top KNOWN sector 20%) + 10 (unknown >= 50%)
    assert score == 40
    unknown = next(f for f in flags if f.flag_id == "unknown_sectors")
    assert unknown.tickers == ["AAA", "BBB"]
    # "Unknown" must never trigger the sector-concentration flag itself.
    assert "sector_concentration" not in {f.flag_id for f in flags}


def test_empty_portfolio_scores_zero():
    assert compute_risk([], []) == (0, "low", [])


# --- Macro calendar (pure) ------------------------------------------------------------


def test_first_friday():
    assert first_friday(2026, 7) == date(2026, 7, 3)
    assert first_friday(2026, 8) == date(2026, 8, 7)


def test_static_events_window_with_fomc():
    events = static_events(date(2026, 7, 27))  # window 07-27..08-03
    types = [(e.event_type, e.date) for e in events]
    assert ("FOMC", date(2026, 7, 29)) in types
    fomc = next(e for e in events if e.event_type == "FOMC")
    assert fomc.approximate is False and fomc.source == "static"


def test_static_events_window_with_cpi_and_nfp():
    events = static_events(date(2026, 8, 6))  # window 08-06..08-13
    assert [(e.event_type, e.date, e.approximate) for e in events] == [
        ("NFP", date(2026, 8, 7), False),
        ("CPI", date(2026, 8, 12), True),
    ]


def test_static_events_empty_window():
    assert static_events(date(2026, 7, 17)) == []  # 07-17..07-24: nothing


def test_match_sensitivity():
    sectors = [
        SectorWeight(sector="Semiconductors", weight_pct=Decimal("50"), tickers=["NVDA", "AMD"]),
        SectorWeight(sector="Retail", weight_pct=Decimal("30"), tickers=["COST"]),
        SectorWeight(sector="Unknown", weight_pct=Decimal("20"), tickers=["XXX"]),
    ]
    sensitive, affected = match_sensitivity("FOMC", sectors)
    assert sensitive == ["Semiconductors"]
    assert affected == ["AMD", "NVDA"]
    sensitive, affected = match_sensitivity("NFP", sectors)
    assert sensitive == ["Retail"] and affected == ["COST"]
    assert match_sensitivity("other", sectors) == ([], [])


# --- Endpoints ---------------------------------------------------------------------


async def test_get_returns_404_when_no_report_exists(client):
    response = await client.get("/portfolio/protect")
    assert response.status_code == 404


async def test_refresh_then_get_roundtrip(client, fake_finnhub, fake_claude):
    await create_position(client, ticker="AAPL", quantity="10", price="150.00")
    await create_position(client, ticker="MSFT", quantity="2", price="300.00")
    fake_finnhub.quotes = {"AAPL": Decimal("200.00"), "MSFT": Decimal("400.00")}
    fake_finnhub.profiles = {
        "AAPL": {"finnhubIndustry": "Technology"},
        "MSFT": {"finnhubIndustry": "Technology"},
    }

    refresh = await client.post("/portfolio/protect/refresh")
    assert refresh.status_code == 200
    assert fake_claude.calls == 1

    response = await client.get("/portfolio/protect")
    assert response.status_code == 200
    content = response.json()["content"]
    assert content["text"] == "Fake report text"

    data = content["data"]
    assert data["position_count"] == 2
    assert data["total_value"] == "2800.00"  # 10*200 + 2*400
    top = data["positions"][0]
    assert top["ticker"] == "AAPL"
    assert top["weight_pct"] == "71.43"
    assert top["weight_basis"] == "market"
    assert data["sectors"][0]["sector"] == "Technology"
    assert data["sectors"][0]["weight_pct"] == "100.00"
    # 40 (top position >= 40%) + 30 (top sector >= 60%) + 20 (<= 2 positions)
    assert data["risk_score"] == 90
    assert data["risk_level"] == "high"
    assert {f["flag_id"] for f in data["flags"]} == {
        "position_concentration", "sector_concentration", "low_diversification",
    }


async def test_free_tier_calendar_403_keeps_static_events(
    client, fake_finnhub, monkeypatch
):
    """The normal free-tier case: Finnhub calendar 403s, static events stand."""
    await create_position(client, ticker="AAPL")
    fake_finnhub.quotes = {"AAPL": Decimal("200.00")}
    fake_finnhub.calendar_error = FinnhubAuthError("403")
    # Pin "today" so a static event is guaranteed inside the 7-day window.
    monkeypatch.setattr("app.services.protect.today_ny", lambda: date(2026, 7, 27))

    response = await client.post("/portfolio/protect/refresh")
    assert response.status_code == 200
    content = response.json()["content"]
    assert "economic_calendar_unavailable" in content["warnings"]
    events = content["data"]["macro_events"]
    assert [(e["event_type"], e["date"]) for e in events] == [
        ("FOMC", "2026-07-29"), ("NFP", "2026-08-07")
    ][:len(events)]
    fomc = events[0]
    # AAPL is Technology (conftest default profile) -> FOMC-sensitive.
    assert fomc["sensitive_sectors"] == ["Technology"]
    assert fomc["affected_tickers"] == ["AAPL"]


async def test_finnhub_events_merged_and_deduped(client, fake_finnhub, monkeypatch):
    await create_position(client, ticker="AAPL")
    fake_finnhub.quotes = {"AAPL": Decimal("200.00")}
    monkeypatch.setattr("app.services.protect.today_ny", lambda: date(2026, 7, 17))
    fake_finnhub.economic_events = [
        # Duplicates the static CPI type -> dropped.
        {"country": "US", "impact": "high", "event": "CPI m/m", "time": "2026-07-20 08:30:00"},
        # Low impact -> dropped.
        {"country": "US", "impact": "low", "event": "Existing Home Sales", "time": "2026-07-21 10:00:00"},
        # Non-US -> dropped.
        {"country": "DE", "impact": "high", "event": "German ZEW", "time": "2026-07-21 05:00:00"},
        # Kept as "other".
        {"country": "US", "impact": "high", "event": "Retail Sales", "time": "2026-07-21 08:30:00"},
    ]

    response = await client.post("/portfolio/protect/refresh")
    assert response.status_code == 200
    events = response.json()["content"]["data"]["macro_events"]
    assert [(e["event_type"], e["title"], e["source"]) for e in events] == [
        ("other", "Retail Sales", "finnhub")
    ]


async def test_profile_failure_degrades_to_unknown_sector(client, fake_finnhub):
    await create_position(client, ticker="AAPL")
    fake_finnhub.quotes = {"AAPL": Decimal("200.00")}
    fake_finnhub.profile_error = FinnhubAuthError("403")

    response = await client.post("/portfolio/protect/refresh")
    assert response.status_code == 200
    content = response.json()["content"]
    assert "sector_unavailable:AAPL" in content["warnings"]
    data = content["data"]
    assert data["positions"][0]["sector"] == "Unknown"
    assert "unknown_sectors" in {f["flag_id"] for f in data["flags"]}


async def test_quote_failure_uses_cost_basis(client, fake_finnhub):
    await create_position(client, ticker="AAPL", quantity="10", price="150.00")
    fake_finnhub.quotes = {}  # every quote fails

    response = await client.post("/portfolio/protect/refresh")
    assert response.status_code == 200
    content = response.json()["content"]
    assert "weight_uses_cost_basis:AAPL" in content["warnings"]
    position = content["data"]["positions"][0]
    assert position["weight_basis"] == "cost"
    assert position["value"] == "1500.00"
    assert content["data"]["total_value"] == "1500.00"


async def test_empty_portfolio_is_a_valid_report(client, fake_claude):
    response = await client.post("/portfolio/protect/refresh")
    assert response.status_code == 200
    data = response.json()["content"]["data"]
    assert data["position_count"] == 0
    assert data["total_value"] is None
    assert data["risk_score"] == 0
    assert data["risk_level"] == "low"
    assert data["positions"] == [] and data["flags"] == []
    assert fake_claude.calls == 1


async def test_refresh_twice_upserts_single_row(client, fake_finnhub, fake_claude, session_factory):
    await create_position(client, ticker="AAPL")
    fake_finnhub.quotes = {"AAPL": Decimal("200.00")}
    first = await client.post("/portfolio/protect/refresh")
    second = await client.post("/portfolio/protect/refresh")
    assert first.status_code == second.status_code == 200
    assert await _count_reports(session_factory) == 1
    assert fake_claude.calls == 2  # force=True regenerates


async def test_scheduler_path_returns_cached_report(session_factory, fake_finnhub, fake_claude):
    """force=False (the scheduler's mode) must not re-call Claude on the same day."""
    async with session_factory() as session:
        await generate_protect(session, fake_finnhub, fake_claude)
        await generate_protect(session, fake_finnhub, fake_claude)
    assert fake_claude.calls == 1


async def test_claude_failure_returns_503_and_writes_nothing(
    client, fake_claude, session_factory
):
    fake_claude.raise_on_call = ClaudeUnavailableError("Anthropic did not respond")
    response = await client.post("/portfolio/protect/refresh")
    assert response.status_code == 503
    assert await _count_reports(session_factory) == 0


async def test_claude_rate_limit_returns_429(client, fake_claude):
    fake_claude.raise_on_call = ClaudeRateLimitError("429")
    response = await client.post("/portfolio/protect/refresh")
    assert response.status_code == 429
