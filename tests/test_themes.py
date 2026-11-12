from decimal import Decimal

from app.services.finnhub_client import FinnhubUnavailableError
from app.services.themes import THEMES


# --- Static data sanity --------------------------------------------------------------


def test_theme_slugs_unique_and_tickers_wellformed():
    slugs = [theme.slug for theme in THEMES]
    assert len(slugs) == len(set(slugs))
    for theme in THEMES:
        assert theme.name and theme.description
        assert theme.tickers, f"theme {theme.slug} has no tickers"
        for ticker in theme.tickers:
            assert ticker == ticker.upper() and ticker.isalpha()
        assert len(theme.tickers) == len(set(theme.tickers))


# --- Endpoints -------------------------------------------------------------------------


async def test_list_themes(client):
    response = await client.get("/themes")
    assert response.status_code == 200
    body = response.json()
    assert {t["slug"] for t in body["themes"]} == {t.slug for t in THEMES}
    space = next(t for t in body["themes"] if t["slug"] == "space")
    assert space["name"] == "Uzay Teknolojileri"
    assert space["ticker_count"] == 5
    assert "istatistiksel" in body["disclaimer"]


async def test_theme_detail_enriched(client, fake_finnhub):
    fake_finnhub.quotes["RKLB"] = Decimal("28.50")
    fake_finnhub.pct_changes["RKLB"] = Decimal("2.10")
    fake_finnhub.profiles["RKLB"] = {"finnhubIndustry": "Aerospace & Defense"}

    response = await client.get("/themes/space")
    assert response.status_code == 200
    body = response.json()
    rklb = next(s for s in body["stocks"] if s["ticker"] == "RKLB")
    assert rklb["price"] == "28.50"
    assert rklb["percent_change"] == "2.10"
    assert rklb["industry"] == "Aerospace & Defense"
    assert rklb["price_status"] == "ok"
    # The other tickers have no fake quote -> degraded, not failed.
    others = [s for s in body["stocks"] if s["ticker"] != "RKLB"]
    assert all(s["price_status"] == "unavailable" for s in others)
    assert all(f"quote_unavailable:{s['ticker']}" in body["warnings"] for s in others)
    assert "istatistiksel" in body["disclaimer"]


async def test_theme_detail_total_blackout_still_200(client, fake_finnhub):
    fake_finnhub.raise_on_call = FinnhubUnavailableError("down")
    fake_finnhub.profile_error = FinnhubUnavailableError("down")

    response = await client.get("/themes/ai")
    assert response.status_code == 200
    body = response.json()
    assert all(s["price_status"] == "unavailable" for s in body["stocks"])
    assert len(body["stocks"]) == 6  # the curated list itself still serves


async def test_unknown_theme_404(client):
    response = await client.get("/themes/crypto")
    assert response.status_code == 404
