from datetime import timedelta
from decimal import Decimal

from app.core.timeutils import today_ny
from app.services.finnhub_client import FinnhubAuthError
from app.services.technical import classify_technical
from app.services.yahoo_client import YahooRateLimitError

from .conftest import make_closes


async def create_position(client, ticker="AAPL", quantity="10", price="150.00"):
    response = await client.post(
        "/positions",
        json={"ticker": ticker, "quantity": quantity, "purchase_price": price},
    )
    assert response.status_code == 201
    return response


# --- classify_technical (pure rule) ------------------------------------------------


def test_classify_strong():
    assert classify_technical(True, Decimal("-5"), Decimal("40")) == "strong"
    assert classify_technical(True, Decimal("-10"), Decimal("40")) == "strong"  # boundary


def test_classify_weak():
    assert classify_technical(False, Decimal("-30"), Decimal("5")) == "weak"
    assert classify_technical(False, Decimal("-30"), Decimal("10")) == "weak"  # boundary


def test_classify_neutral():
    assert classify_technical(True, Decimal("-20"), Decimal("40")) == "neutral"
    assert classify_technical(False, Decimal("-20"), Decimal("40")) == "neutral"


def test_classify_missing_inputs():
    assert classify_technical(None, Decimal("-5"), Decimal("40")) is None
    assert classify_technical(True, None, Decimal("40")) is None
    assert classify_technical(True, Decimal("-5"), None) is None


# --- GET /portfolio/technical --------------------------------------------------------


async def test_technical_happy_path_strong(client):
    # Default FakeYahoo ramp: last 125.90, ma50 123.45, ma200 115.95,
    # 252-session window 100.80..125.90.
    await create_position(client, ticker="AAPL")

    response = await client.get("/portfolio/technical")
    assert response.status_code == 200
    body = response.json()
    assert body["as_of_date"] == today_ny().isoformat()

    stock = body["stocks"][0]
    assert stock["ticker"] == "AAPL"
    assert stock["data_status"] == "ok"
    assert Decimal(stock["close"]) == Decimal("125.90")
    assert Decimal(stock["high_52w"]) == Decimal("125.90")
    assert Decimal(stock["low_52w"]) == Decimal("100.80")
    assert Decimal(stock["pct_from_high_52w"]) == Decimal("0.00")
    assert Decimal(stock["pct_from_low_52w"]) == Decimal("24.90")
    assert Decimal(stock["ma50"]) == Decimal("123.45")
    assert Decimal(stock["ma200"]) == Decimal("115.95")
    assert stock["above_ma50"] is True
    assert stock["above_ma200"] is True
    assert Decimal(stock["pct_from_ma200"]) == Decimal("8.58")
    assert stock["label"] == "strong"
    assert stock["earnings_this_week"] is False  # calendar worked, no entries
    assert body["warnings"] == []


async def test_technical_weak_label(client, fake_yahoo):
    # Descending ramp: below MA200 and sitting on the 52-week low.
    fake_yahoo.closes["AAPL"] = [
        Decimal("100") - Decimal("0.1") * i for i in range(260)
    ]
    await create_position(client, ticker="AAPL")

    response = await client.get("/portfolio/technical")
    stock = response.json()["stocks"][0]
    assert stock["above_ma200"] is False
    assert Decimal(stock["pct_from_low_52w"]) == Decimal("0.00")
    assert stock["label"] == "weak"


async def test_technical_neutral_label(client, fake_yahoo):
    # Above MA200 (recent history averages lower) but 26.7% off the old high.
    fake_yahoo.closes["AAPL"] = (
        [Decimal("150")] * 60 + [Decimal("100")] * 195 + [Decimal("110")] * 5
    )
    await create_position(client, ticker="AAPL")

    response = await client.get("/portfolio/technical")
    stock = response.json()["stocks"][0]
    assert stock["above_ma200"] is True
    assert Decimal(stock["pct_from_high_52w"]) < Decimal("-10")
    assert stock["label"] == "neutral"


async def test_technical_insufficient_history_degrades(client, fake_yahoo):
    fake_yahoo.closes["AAPL"] = make_closes(120)  # enough for MA50 only
    await create_position(client, ticker="AAPL")

    response = await client.get("/portfolio/technical")
    assert response.status_code == 200
    body = response.json()
    stock = body["stocks"][0]
    assert stock["data_status"] == "ok"
    assert stock["ma50"] is not None
    assert stock["ma200"] is None
    assert stock["high_52w"] is None
    assert stock["label"] is None
    assert "technical_insufficient_history:AAPL" in body["warnings"]


async def test_technical_one_ticker_unavailable(client, fake_yahoo):
    fake_yahoo.raise_for = {"MSFT"}
    await create_position(client, ticker="AAPL")
    await create_position(client, ticker="MSFT")

    response = await client.get("/portfolio/technical")
    assert response.status_code == 200
    body = response.json()
    by_ticker = {s["ticker"]: s for s in body["stocks"]}
    assert by_ticker["AAPL"]["data_status"] == "ok"
    assert by_ticker["MSFT"]["data_status"] == "unavailable"
    assert by_ticker["MSFT"]["close"] is None
    assert by_ticker["MSFT"]["label"] is None
    assert "candles_unavailable:MSFT" in body["warnings"]


async def test_technical_rate_limit_all_failed_is_429(client, fake_yahoo):
    fake_yahoo.errors["AAPL"] = YahooRateLimitError("429")
    await create_position(client, ticker="AAPL")

    response = await client.get("/portfolio/technical")
    assert response.status_code == 429


async def test_technical_all_failed_is_503(client, fake_yahoo):
    fake_yahoo.raise_for = {"AAPL"}
    await create_position(client, ticker="AAPL")

    response = await client.get("/portfolio/technical")
    assert response.status_code == 503


async def test_technical_rate_limit_mid_run_partial(client, fake_yahoo):
    # Tickers are fetched sorted: AAPL succeeds, MSFT 429s -> abort, still 200.
    fake_yahoo.errors["MSFT"] = YahooRateLimitError("429")
    await create_position(client, ticker="AAPL")
    await create_position(client, ticker="MSFT")

    response = await client.get("/portfolio/technical")
    assert response.status_code == 200
    body = response.json()
    by_ticker = {s["ticker"]: s for s in body["stocks"]}
    assert by_ticker["AAPL"]["data_status"] == "ok"
    assert by_ticker["MSFT"]["data_status"] == "unavailable"
    assert "technical_aborted_rate_limit" in body["warnings"]
    assert fake_yahoo.calls == ["AAPL", "MSFT"]


async def test_technical_earnings_flag(client, fake_finnhub):
    report_date = today_ny() + timedelta(days=3)
    fake_finnhub.earnings = [{"symbol": "AAPL", "date": report_date.isoformat()}]
    await create_position(client, ticker="AAPL")
    await create_position(client, ticker="MSFT")

    response = await client.get("/portfolio/technical")
    by_ticker = {s["ticker"]: s for s in response.json()["stocks"]}
    assert by_ticker["AAPL"]["earnings_this_week"] is True
    assert by_ticker["AAPL"]["earnings_date"] == report_date.isoformat()
    assert by_ticker["MSFT"]["earnings_this_week"] is False
    assert by_ticker["MSFT"]["earnings_date"] is None


async def test_technical_earnings_calendar_403_degrades(client, fake_finnhub):
    fake_finnhub.calendar_error = FinnhubAuthError("403")
    await create_position(client, ticker="AAPL")

    response = await client.get("/portfolio/technical")
    assert response.status_code == 200
    body = response.json()
    assert body["stocks"][0]["earnings_this_week"] is None
    assert "earnings_calendar_unavailable" in body["warnings"]


async def test_technical_empty_portfolio(client, fake_yahoo):
    response = await client.get("/portfolio/technical")
    assert response.status_code == 200
    body = response.json()
    assert body["stocks"] == []
    assert fake_yahoo.calls == []


async def test_technical_memo_cache_skips_refetch(client, fake_yahoo):
    await create_position(client, ticker="AAPL")

    assert (await client.get("/portfolio/technical")).status_code == 200
    calls_after_first = len(fake_yahoo.calls)
    assert (await client.get("/portfolio/technical")).status_code == 200
    assert len(fake_yahoo.calls) == calls_after_first


async def test_technical_duplicate_ticker_positions(client, fake_yahoo):
    await create_position(client, ticker="AAPL", quantity="10")
    await create_position(client, ticker="AAPL", quantity="5")

    response = await client.get("/portfolio/technical")
    body = response.json()
    assert [s["ticker"] for s in body["stocks"]] == ["AAPL"]
    assert fake_yahoo.calls == ["AAPL"]
