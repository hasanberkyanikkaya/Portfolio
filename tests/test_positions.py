from decimal import Decimal

from app.services.finnhub_client import FinnhubRateLimitError, FinnhubUnavailableError


async def create_position(client, ticker="AAPL", quantity="10", price="150.00"):
    return await client.post(
        "/positions",
        json={"ticker": ticker, "quantity": quantity, "purchase_price": price},
    )


async def test_create_position(client):
    response = await create_position(client, ticker="aapl")
    assert response.status_code == 201
    body = response.json()
    assert body["ticker"] == "AAPL"  # normalized to uppercase
    assert Decimal(body["quantity"]) == Decimal("10")
    assert Decimal(body["purchase_price"]) == Decimal("150.00")
    assert body["purchase_date"] is not None
    assert body["id"] == 1


async def test_create_position_rejects_non_nasdaq_ticker(client):
    response = await create_position(client, ticker="NOPE")
    assert response.status_code == 400
    assert "NASDAQ" in response.json()["detail"]


async def test_create_position_when_finnhub_is_down(client, fake_finnhub):
    fake_finnhub.raise_on_call = FinnhubUnavailableError("timeout")
    response = await create_position(client)
    assert response.status_code == 503


async def test_create_position_when_rate_limited(client, fake_finnhub):
    fake_finnhub.raise_on_call = FinnhubRateLimitError("429")
    response = await create_position(client)
    assert response.status_code == 429


async def test_create_position_rejects_bad_values(client):
    response = await client.post(
        "/positions",
        json={"ticker": "AAPL", "quantity": "-5", "purchase_price": "150.00"},
    )
    assert response.status_code == 422


async def test_list_positions_with_pnl(client, fake_finnhub):
    fake_finnhub.quotes["AAPL"] = Decimal("165.00")
    await create_position(client, ticker="AAPL", quantity="10", price="150.00")

    response = await client.get("/positions")
    assert response.status_code == 200
    body = response.json()

    position = body["positions"][0]
    assert position["price_status"] == "ok"
    assert Decimal(position["current_price"]) == Decimal("165.00")
    assert Decimal(position["cost_basis"]) == Decimal("1500.00")
    assert Decimal(position["market_value"]) == Decimal("1650.00")
    assert Decimal(position["unrealized_pnl"]) == Decimal("150.00")
    assert Decimal(position["unrealized_pnl_pct"]) == Decimal("10.00")

    assert Decimal(body["total_cost_basis"]) == Decimal("1500.00")
    assert Decimal(body["total_market_value"]) == Decimal("1650.00")
    assert Decimal(body["total_unrealized_pnl"]) == Decimal("150.00")


async def test_list_positions_degrades_when_finnhub_fails(client, fake_finnhub):
    await create_position(client)  # no quote configured -> price fetch fails

    response = await client.get("/positions")
    assert response.status_code == 200
    body = response.json()

    position = body["positions"][0]
    assert position["price_status"] == "unavailable"
    assert position["current_price"] is None
    assert position["unrealized_pnl"] is None
    assert Decimal(body["total_cost_basis"]) == Decimal("1500.00")
    assert body["total_market_value"] is None
    assert body["total_unrealized_pnl"] is None


async def test_close_position_creates_realized_trade(client):
    await create_position(client, ticker="AAPL", quantity="10", price="150.00")

    response = await client.post("/positions/1/close", json={"sale_price": "180.50"})
    assert response.status_code == 200
    trade = response.json()
    assert trade["ticker"] == "AAPL"
    assert Decimal(trade["realized_pnl"]) == Decimal("305.00")  # (180.50-150)*10

    # Position is gone from the open list.
    open_positions = (await client.get("/positions")).json()["positions"]
    assert open_positions == []


async def test_close_missing_position_returns_404(client):
    response = await client.post("/positions/999/close", json={"sale_price": "10"})
    assert response.status_code == 404


async def test_realized_trades_list_and_total(client):
    await create_position(client, ticker="AAPL", quantity="10", price="150.00")
    await create_position(client, ticker="MSFT", quantity="5", price="300.00")
    await client.post("/positions/1/close", json={"sale_price": "180.00"})  # +300
    await client.post("/positions/2/close", json={"sale_price": "290.00"})  # -50

    response = await client.get("/positions/realized")
    assert response.status_code == 200
    body = response.json()
    assert len(body["trades"]) == 2
    assert Decimal(body["total_realized_pnl"]) == Decimal("250.00")


async def test_delete_position_without_trade(client):
    await create_position(client)

    response = await client.delete("/positions/1")
    assert response.status_code == 204

    assert (await client.get("/positions")).json()["positions"] == []
    assert (await client.get("/positions/realized")).json()["trades"] == []


async def test_delete_missing_position_returns_404(client):
    response = await client.delete("/positions/42")
    assert response.status_code == 404
