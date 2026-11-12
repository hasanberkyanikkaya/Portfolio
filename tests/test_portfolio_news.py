from datetime import datetime, timedelta

from app.core.timeutils import NY_TZ
from app.services.finnhub_client import (
    FinnhubRateLimitError,
    FinnhubUnavailableError,
)
from app.services.technical import MAX_NEWS_ITEMS


async def create_position(client, ticker="AAPL"):
    response = await client.post(
        "/positions",
        json={"ticker": ticker, "quantity": "10", "purchase_price": "150.00"},
    )
    assert response.status_code == 201


def news_item(headline: str, ts: int, **extra) -> dict:
    return {
        "headline": headline,
        "source": "Reuters",
        "url": "https://example.com/story",
        "summary": "Something happened.",
        "datetime": ts,
        **extra,
    }


async def test_news_happy_path(client, fake_finnhub):
    await create_position(client, ticker="AAPL")
    base = int(datetime.now(NY_TZ).timestamp())
    fake_finnhub.company_news["AAPL"] = [
        news_item("Older story", base - 3600),
        news_item("Newest story", base),
    ]

    response = await client.get("/portfolio/AAPL/news")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert [item["headline"] for item in body["items"]] == ["Newest story", "Older story"]

    newest = body["items"][0]
    assert newest["source"] == "Reuters"
    assert newest["url"] == "https://example.com/story"
    assert newest["summary"] == "Something happened."
    # published_at is tz-aware NY time matching the unix timestamp
    assert datetime.fromisoformat(newest["published_at"]) == datetime.fromtimestamp(
        base, tz=NY_TZ
    )


async def test_news_ticker_not_in_portfolio_is_404(client):
    response = await client.get("/portfolio/AAPL/news")
    assert response.status_code == 404


async def test_news_lowercase_ticker_normalized(client, fake_finnhub):
    await create_position(client, ticker="AAPL")
    fake_finnhub.company_news["AAPL"] = [
        news_item("A story", int(datetime.now(NY_TZ).timestamp()))
    ]

    response = await client.get("/portfolio/aapl/news")
    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"
    assert len(response.json()["items"]) == 1


async def test_news_rate_limited_is_429(client, fake_finnhub):
    await create_position(client, ticker="AAPL")
    fake_finnhub.news_error = FinnhubRateLimitError("429")

    response = await client.get("/portfolio/AAPL/news")
    assert response.status_code == 429


async def test_news_finnhub_down_is_503(client, fake_finnhub):
    await create_position(client, ticker="AAPL")
    fake_finnhub.news_error = FinnhubUnavailableError("timeout")

    response = await client.get("/portfolio/AAPL/news")
    assert response.status_code == 503


async def test_news_caps_items_and_skips_junk(client, fake_finnhub):
    await create_position(client, ticker="AAPL")
    base = int((datetime.now(NY_TZ) - timedelta(hours=1)).timestamp())
    items = [news_item(f"Story {i}", base + i) for i in range(MAX_NEWS_ITEMS + 5)]
    items.append(news_item("", base + 999))  # headline-less junk -> skipped
    fake_finnhub.company_news["AAPL"] = items

    response = await client.get("/portfolio/AAPL/news")
    body = response.json()
    assert len(body["items"]) == MAX_NEWS_ITEMS
    # Newest first: the junk item (would-be newest) was skipped.
    assert body["items"][0]["headline"] == f"Story {MAX_NEWS_ITEMS + 4}"
