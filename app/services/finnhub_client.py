"""Finnhub API client.

All Finnhub calls in the project go through this module (never from routers).
Failure cases are turned into typed exceptions so routers can map them to
proper HTTP responses:

- FinnhubAuthError        -> API key missing or rejected
- FinnhubRateLimitError   -> HTTP 429 from Finnhub (free tier: 60 calls/min)
- FinnhubUnavailableError -> timeout, connection error, or 5xx from Finnhub
- FinnhubError            -> base class / any other Finnhub problem
"""

import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import httpx

from app.core.config import get_settings

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
REQUEST_TIMEOUT_SECONDS = 10.0

# The free tier has no real index symbols (^GSPC etc.), so the daily reports
# use these ETFs as index proxies.
INDEX_PROXIES: dict[str, str] = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "DIA": "Dow Jones",
}


class FinnhubError(Exception):
    """Base error for anything that goes wrong talking to Finnhub."""


class FinnhubAuthError(FinnhubError):
    pass


class FinnhubRateLimitError(FinnhubError):
    pass


class FinnhubUnavailableError(FinnhubError):
    pass


@dataclass
class Quote:
    current_price: Decimal
    change: Decimal | None
    percent_change: Decimal | None
    previous_close: Decimal | None


def _to_decimal(value) -> Decimal | None:
    # Finnhub returns floats; go through str() to avoid float artifacts.
    return None if value is None else Decimal(str(value))


class FinnhubClient:
    def __init__(self, api_key: str, base_url: str = FINNHUB_BASE_URL) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(base_url=base_url, timeout=REQUEST_TIMEOUT_SECONDS)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict) -> dict | list:
        if not self._api_key:
            raise FinnhubAuthError("FINNHUB_API_KEY is not set in .env")

        try:
            response = await self._client.get(path, params={**params, "token": self._api_key})
        except httpx.HTTPError as exc:
            raise FinnhubUnavailableError(f"Finnhub did not respond: {exc}") from exc

        if response.status_code == 429:
            raise FinnhubRateLimitError("Finnhub rate limit exceeded (60 calls/min on free tier)")
        if response.status_code in (401, 403):
            raise FinnhubAuthError("Finnhub rejected the API key")
        if response.status_code >= 500:
            raise FinnhubUnavailableError(f"Finnhub server error: {response.status_code}")
        if response.status_code >= 400:
            raise FinnhubError(f"Finnhub error {response.status_code}: {response.text[:200]}")

        return response.json()

    async def get_quote(self, symbol: str) -> Quote:
        """Real-time quote. Raises FinnhubError if the symbol has no quote data."""
        data = await self._get("/quote", {"symbol": symbol})
        current = data.get("c")
        # Finnhub returns all-zero quotes for unknown symbols.
        if not current:
            raise FinnhubError(f"No quote data for '{symbol}'")
        return Quote(
            current_price=_to_decimal(current),
            change=_to_decimal(data.get("d")),
            percent_change=_to_decimal(data.get("dp")),
            previous_close=_to_decimal(data.get("pc")),
        )

    async def is_nasdaq_ticker(self, symbol: str) -> bool:
        """True if the symbol exists (symbol lookup) and is listed on NASDAQ.

        Finnhub's /search endpoint does not include the listing exchange, so we
        confirm NASDAQ membership with a second call to /stock/profile2.
        """
        data = await self._get("/search", {"q": symbol, "exchange": "US"})
        results = data.get("result", []) if isinstance(data, dict) else []
        if not any(item.get("symbol", "").upper() == symbol.upper() for item in results):
            return False

        profile = await self._get("/stock/profile2", {"symbol": symbol})
        exchange = (profile.get("exchange") or "") if isinstance(profile, dict) else ""
        return "NASDAQ" in exchange.upper()

    async def get_index_quotes(self) -> dict[str, Quote | None]:
        """Quotes for the index-proxy ETFs (see INDEX_PROXIES).

        One failed symbol must not sink a whole report: failed symbols map to
        None. Raises only if EVERY symbol fails (so callers can record a warning).
        """
        symbols = list(INDEX_PROXIES)
        results = await asyncio.gather(
            *(self.get_quote(s) for s in symbols), return_exceptions=True
        )
        quotes = {
            symbol: (result if isinstance(result, Quote) else None)
            for symbol, result in zip(symbols, results)
        }
        if all(q is None for q in quotes.values()):
            first_error = next(r for r in results if isinstance(r, BaseException))
            if isinstance(first_error, FinnhubError):
                raise first_error
            raise FinnhubError(f"No index quotes available: {first_error}")
        return quotes

    async def get_company_profile(self, symbol: str) -> dict:
        """Company profile2 (free tier). Callers read `finnhubIndustry` for the
        sector; an empty dict / missing key degrades to sector "Unknown"."""
        data = await self._get("/stock/profile2", {"symbol": symbol})
        return data if isinstance(data, dict) else {}

    async def get_economic_calendar(self, from_date: date, to_date: date) -> list[dict]:
        """Economic calendar events. Premium endpoint — 403 on the free tier
        (surfaces as FinnhubAuthError; report generation records a warning)."""
        data = await self._get(
            "/calendar/economic",
            {"from": from_date.isoformat(), "to": to_date.isoformat()},
        )
        return data.get("economicCalendar", []) if isinstance(data, dict) else []

    async def get_earnings_calendar(self, from_date: date, to_date: date) -> list[dict]:
        """Earnings calendar. Limited/premium on the free tier — same graceful
        handling as get_economic_calendar."""
        data = await self._get(
            "/calendar/earnings",
            {"from": from_date.isoformat(), "to": to_date.isoformat()},
        )
        return data.get("earningsCalendar", []) if isinstance(data, dict) else []

    async def get_company_news(self, symbol: str, from_date: date, to_date: date) -> list[dict]:
        """Company news (available on the free tier for US symbols). Items carry
        headline, source, url, summary and a unix-seconds `datetime`."""
        data = await self._get(
            "/company-news",
            {"symbol": symbol, "from": from_date.isoformat(), "to": to_date.isoformat()},
        )
        return data if isinstance(data, list) else []


_client: FinnhubClient | None = None


def get_finnhub_client() -> FinnhubClient:
    """FastAPI dependency — one shared client for the whole process."""
    global _client
    if _client is None:
        _client = FinnhubClient(get_settings().finnhub_api_key)
    return _client


async def close_finnhub_client() -> None:
    """Close the shared client (called from the app lifespan on shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
