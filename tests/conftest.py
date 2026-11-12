from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.timeutils import today_ny
from app.main import app
from app.models import Base
from app.services.claude_client import get_claude_client
from app.services.finnhub_client import FinnhubError, Quote, get_finnhub_client
from app.services.protect import clear_protect_cache
from app.services.sentiment import SENTIMENT_BASKET
from app.services.technical import clear_technical_cache
from app.services.yahoo_client import Candle, YahooError, get_yahoo_client

# Symbols the Market Pulse report fetches candles for (12 sectors + RSP/SPY/QQQ).
MARKET_PULSE_CANDLE_SYMBOLS = [
    "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE",
    "SMH", "XBI", "RSP", "SPY", "QQQ",
]

# Symbols the Sentiment report fetches candles for (SPY is already above).
SENTIMENT_CANDLE_SYMBOLS = ["^VIX", *SENTIMENT_BASKET]


def make_closes(
    n: int = 260, start: Decimal = Decimal("100"), step: Decimal = Decimal("0.1")
) -> list[Decimal]:
    """Deterministic price ramp -> exactly predictable MAs and weekly change:
    last close 125.90, ma50 123.45, ma200 115.95, weekly change 0.40%."""
    return [start + step * i for i in range(n)]


class FakeFinnhub:
    """In-memory stand-in for FinnhubClient so tests need no network/API key."""

    def __init__(self) -> None:
        self.nasdaq_tickers: set[str] = {"AAPL", "MSFT", "NVDA"}
        self.quotes: dict[str, Decimal] = {}
        # Per-symbol percent_change for get_quote (Market Pulse daily changes).
        self.pct_changes: dict[str, Decimal] = {}
        self.raise_on_call: Exception | None = None
        # Separate switch for the calendar endpoints (premium on the free tier),
        # so a test can fail the calendars while index quotes still work.
        self.calendar_error: Exception | None = None
        # Earnings calendar entries returned by get_earnings_calendar.
        self.earnings: list[dict] = []
        # Per-symbol company news + a separate failure switch for it.
        self.company_news: dict[str, list[dict]] = {}
        self.news_error: Exception | None = None
        # Economic-calendar entries (Protect macro merge) — still honors
        # calendar_error, mirroring the earnings calendar above.
        self.economic_events: list[dict] = []
        # Per-symbol /stock/profile2 payloads + a separate failure switch.
        # Unknown symbols fall back to a Technology profile so Protect tests
        # get sectors without wiring every ticker explicitly.
        self.profiles: dict[str, dict] = {}
        self.profile_error: Exception | None = None

    async def is_nasdaq_ticker(self, symbol: str) -> bool:
        if self.raise_on_call:
            raise self.raise_on_call
        return symbol.upper() in self.nasdaq_tickers

    async def get_quote(self, symbol: str) -> Quote:
        if self.raise_on_call:
            raise self.raise_on_call
        price = self.quotes.get(symbol.upper())
        if price is None:
            raise FinnhubError(f"No quote data for '{symbol}'")
        return Quote(
            current_price=price,
            change=None,
            percent_change=self.pct_changes.get(symbol.upper()),
            previous_close=None,
        )

    async def get_index_quotes(self) -> dict[str, Quote | None]:
        if self.raise_on_call:
            raise self.raise_on_call
        return {
            "SPY": Quote(
                current_price=Decimal("500.00"),
                change=Decimal("1.20"),
                percent_change=Decimal("0.24"),
                previous_close=Decimal("498.80"),
            ),
            "QQQ": Quote(
                current_price=Decimal("430.00"),
                change=Decimal("-2.10"),
                percent_change=Decimal("-0.49"),
                previous_close=Decimal("432.10"),
            ),
            "DIA": Quote(
                current_price=Decimal("390.00"),
                change=Decimal("0.50"),
                percent_change=Decimal("0.13"),
                previous_close=Decimal("389.50"),
            ),
        }

    async def get_economic_calendar(self, from_date, to_date) -> list[dict]:
        if self.calendar_error:
            raise self.calendar_error
        return self.economic_events

    async def get_earnings_calendar(self, from_date, to_date) -> list[dict]:
        if self.calendar_error:
            raise self.calendar_error
        return self.earnings

    async def get_company_news(self, symbol, from_date, to_date) -> list[dict]:
        if self.news_error:
            raise self.news_error
        return self.company_news.get(symbol.upper(), [])

    async def get_company_profile(self, symbol: str) -> dict:
        if self.profile_error:
            raise self.profile_error
        return self.profiles.get(symbol.upper(), {"finnhubIndustry": "Technology"})


class FakeYahoo:
    """In-memory stand-in for YahooClient — a deterministic ramp per symbol."""

    def __init__(self) -> None:
        self.closes: dict[str, list[Decimal]] = {
            symbol: make_closes()
            for symbol in MARKET_PULSE_CANDLE_SYMBOLS + SENTIMENT_CANDLE_SYMBOLS
        }
        self.raise_on_call: Exception | None = None
        self.raise_for: set[str] = set()
        # Per-symbol typed errors (checked before raise_for) — lets a test
        # inject e.g. a YahooRateLimitError for one basket symbol.
        self.errors: dict[str, Exception] = {}
        self.calls: list[str] = []  # fetch order, for early-abort assertions

    async def get_daily_closes(self, symbol: str) -> list[Candle]:
        self.calls.append(symbol)
        if self.raise_on_call:
            raise self.raise_on_call
        if symbol in self.errors:
            raise self.errors[symbol]
        if symbol in self.raise_for:
            raise YahooError(f"No candle data for '{symbol}'")
        closes = self.closes.get(symbol)
        if closes is None:
            raise YahooError(f"No candle data for '{symbol}'")
        end = today_ny()
        return [
            Candle(date=end - timedelta(days=len(closes) - 1 - i), close=close)
            for i, close in enumerate(closes)
        ]


class FakeClaude:
    """In-memory stand-in for ClaudeClient — counts calls, returns canned text."""

    def __init__(self) -> None:
        self.calls = 0
        self.response = "Fake report text"
        self.raise_on_call: Exception | None = None

    async def generate(self, system: str, user_content: str, max_tokens: int = 2000) -> str:
        if self.raise_on_call:
            raise self.raise_on_call
        self.calls += 1
        return self.response


@pytest.fixture
def fake_finnhub() -> FakeFinnhub:
    return FakeFinnhub()


@pytest.fixture
def fake_yahoo() -> FakeYahoo:
    return FakeYahoo()


@pytest.fixture
def fake_claude() -> FakeClaude:
    return FakeClaude()


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client(fake_finnhub, fake_yahoo, fake_claude, session_factory):
    async def _get_db():
        async with session_factory() as session:
            yield session

    # The technical/protect memo caches live below the DI layer — without
    # this, fake data fetched in one test would leak into the next.
    clear_technical_cache()
    clear_protect_cache()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_finnhub_client] = lambda: fake_finnhub
    app.dependency_overrides[get_yahoo_client] = lambda: fake_yahoo
    app.dependency_overrides[get_claude_client] = lambda: fake_claude
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()
