"""Yahoo Finance daily-candle client.

Free and keyless: https://query1.finance.yahoo.com/v8/finance/chart/SPY
?range=2y&interval=1d returns JSON with daily timestamps and closes. Used for
what the Finnhub free tier cannot provide (historical closes for weekly
performance and the 50/200-day moving averages — Finnhub's /stock/candle is a
premium endpoint). Stooq was the first choice but now fronts its CSV endpoint
with a JavaScript anti-bot challenge, so it is unusable programmatically.

The API is unofficial: it requires a browser-like User-Agent (the default
python/curl UA gets 429) and has no published rate limits, so callers must
fetch symbols SEQUENTIALLY (Market Pulse needs ~15 fetches once a day; latency
is irrelevant at 16:50 ET).

- YahooRateLimitError  -> HTTP 429 from Yahoo
- YahooUnavailableError-> timeout, connection error, or 5xx from Yahoo
- YahooError           -> base class / unknown symbol / unparsable body
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import httpx

from app.core.timeutils import NY_TZ

YAHOO_BASE_URL = "https://query1.finance.yahoo.com"
REQUEST_TIMEOUT_SECONDS = 15.0

# ~500 trading days — comfortably enough for a 200-day moving average.
HISTORY_RANGE = "2y"

# Yahoo rejects the default httpx/curl User-Agent with 429.
_HEADERS = {"User-Agent": "Mozilla/5.0"}


class YahooError(Exception):
    """Base error for anything that goes wrong talking to Yahoo Finance."""


class YahooRateLimitError(YahooError):
    pass


class YahooUnavailableError(YahooError):
    pass


@dataclass
class Candle:
    date: date
    close: Decimal


class YahooClient:
    def __init__(self, base_url: str = YAHOO_BASE_URL) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=REQUEST_TIMEOUT_SECONDS, headers=_HEADERS
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_daily_closes(self, symbol: str) -> list[Candle]:
        """Daily candles for a US symbol, ascending by date (Date + Close only).

        Raises YahooError if Yahoo has no data for the symbol.
        """
        try:
            response = await self._client.get(
                f"/v8/finance/chart/{symbol}",
                params={"range": HISTORY_RANGE, "interval": "1d"},
            )
        except httpx.HTTPError as exc:
            raise YahooUnavailableError(f"Yahoo Finance did not respond: {exc}") from exc

        if response.status_code == 429:
            raise YahooRateLimitError("Yahoo Finance rate limit exceeded")
        if response.status_code >= 500:
            raise YahooUnavailableError(f"Yahoo Finance server error: {response.status_code}")
        # Unknown symbols come back as 404 with {"chart": {"result": null, "error": ...}}.
        if response.status_code >= 400 and response.status_code != 404:
            raise YahooError(
                f"Yahoo Finance error {response.status_code}: {response.text[:200]}"
            )
        return _parse_chart(symbol, response)


def _parse_chart(symbol: str, response: httpx.Response) -> list[Candle]:
    try:
        chart = response.json().get("chart") or {}
        results = chart.get("result") or []
        if not results:
            raise YahooError(f"No candle data for '{symbol}': {chart.get('error')}")
        result = results[0]
        timestamps = result.get("timestamp") or []
        closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    except (ValueError, AttributeError, IndexError) as exc:
        raise YahooError(f"Unparsable Yahoo response for '{symbol}'") from exc

    candles = [
        # Timestamps are the session's open in UTC seconds; the NY date is the
        # trading day.
        Candle(
            date=datetime.fromtimestamp(ts, tz=NY_TZ).date(),
            close=Decimal(str(close)),
        )
        for ts, close in zip(timestamps, closes)
        if close is not None
    ]
    if len(candles) < 2:
        raise YahooError(f"No candle data for '{symbol}'")
    candles.sort(key=lambda c: c.date)
    return candles


_client: YahooClient | None = None


def get_yahoo_client() -> YahooClient:
    """FastAPI dependency — one shared client for the whole process."""
    global _client
    if _client is None:
        _client = YahooClient()
    return _client


async def close_yahoo_client() -> None:
    """Close the shared client (called from the app lifespan on shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
