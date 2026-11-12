"""Portfolio technical tracking + port news (Phase 6).

Pure-data services — no Claude, no DB cache. For every unique portfolio
ticker we compute, from Yahoo daily closes (Finnhub candles are premium):

- distance from the 52-week closing high/low (%) — same accepted
  approximation as the Sentiment breadth component: "52-week high/low" means
  the closing extreme of the trailing HIGH_LOW_WINDOW (252) sessions.
- MA50 / MA200 position (above/below + % distance), same math as the
  Market Pulse index positioning.
- an earnings-this-week flag from Finnhub's earnings calendar
  ([today, today + EARNINGS_LOOKAHEAD_DAYS] in NY time). The calendar is
  limited/premium on the free tier — any FinnhubError degrades the flag to
  None for every stock with an `earnings_calendar_unavailable` warning.

LABEL RULE (classify_technical; rule-based, Claude is never involved):
- strong  = close above MA200 AND within NEAR_HIGH_PCT (10%) below the 52w high
- weak    = close below MA200 AND within NEAR_LOW_PCT (10%) above the 52w low
- neutral = everything else; any required input missing -> label is None.

Each block degrades independently: 52w needs >= 252 closes, MA200 >= 200,
MA50 >= 50 (warning `technical_insufficient_history:{ticker}`); a failed
Yahoo fetch marks the stock `data_status="unavailable"` (warning
`candles_unavailable:{ticker}`) without failing the endpoint. A Yahoo 429
aborts the remaining fetches (warning `technical_aborted_rate_limit`). Only
when EVERY ticker failed does build_portfolio_technical raise
TechnicalDataUnavailableError (rate_limited decides 429 vs 503).

Yahoo etiquette: fetches are sequential with TICKER_FETCH_DELAY_SECONDS
spacing (see yahoo_client docstring), and daily closes are memoized in-process
per (ticker, NY date) — closes only change once a day, and every page reload
would otherwise re-trigger N sequential fetches against an API that 429s.
Tests must call clear_technical_cache() (the cache lives below the DI layer).
"""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.core.timeutils import NY_TZ, today_ny
from app.schemas.portfolio import (
    NewsItem,
    PortfolioTechnicalResponse,
    StockTechnical,
    TechnicalLabel,
)
from app.services.finnhub_client import FinnhubError
from app.services.market_pulse import pct_distance, sma
from app.services.pnl import money
from app.services.sentiment import HIGH_LOW_WINDOW
from app.services.yahoo_client import Candle, YahooError, YahooRateLimitError

# --- Tunables (see the module docstring) ------------------------------------------
NEAR_HIGH_PCT = Decimal("10")  # "close to the 52w high" = within 10% below it
NEAR_LOW_PCT = Decimal("10")  # "close to the 52w low" = within 10% above it
EARNINGS_LOOKAHEAD_DAYS = 7
TICKER_FETCH_DELAY_SECONDS = 0.25  # same etiquette as sentiment's basket
NEWS_LOOKBACK_DAYS = 7
MAX_NEWS_ITEMS = 20


class TechnicalDataUnavailableError(Exception):
    """Every portfolio ticker failed to fetch — nothing to serve."""

    def __init__(self, rate_limited: bool) -> None:
        self.rate_limited = rate_limited
        super().__init__(
            "Yahoo rate limit hit before any ticker could be fetched"
            if rate_limited
            else "No historical data available for any portfolio ticker"
        )


# In-process memo cache: ticker -> (NY date it was fetched, candles).
_closes_cache: dict[str, tuple[date, list[Candle]]] = {}


def clear_technical_cache() -> None:
    _closes_cache.clear()


# --- Label rule (pure, unit-testable) ----------------------------------------------


def classify_technical(
    above_ma200: bool | None,
    pct_from_high: Decimal | None,
    pct_from_low: Decimal | None,
) -> TechnicalLabel | None:
    if above_ma200 is None or pct_from_high is None or pct_from_low is None:
        return None
    if above_ma200 and pct_from_high >= -NEAR_HIGH_PCT:
        return "strong"
    if not above_ma200 and pct_from_low <= NEAR_LOW_PCT:
        return "weak"
    return "neutral"


# --- Data fetching ------------------------------------------------------------------


async def fetch_daily_closes_cached(
    yahoo, tickers: list[str], warnings: list[str]
) -> tuple[dict[str, list[Candle]], bool]:
    """Sequential, cache-first. Returns (candles per ticker, rate_limited).

    Shared with the Setups scan (services/setups.py) so a setups run reuses
    whatever /portfolio/technical already fetched that NY day and vice versa.
    """
    today = today_ny()
    candles: dict[str, list[Candle]] = {}
    fetched_from_network = False
    for ticker in tickers:
        cached = _closes_cache.get(ticker)
        if cached is not None and cached[0] == today:
            candles[ticker] = cached[1]
            continue
        if fetched_from_network:
            await asyncio.sleep(TICKER_FETCH_DELAY_SECONDS)
        fetched_from_network = True
        try:
            series = await yahoo.get_daily_closes(ticker)
        except YahooRateLimitError:
            # Stop hammering Yahoo — the remaining tickers stay unavailable.
            warnings.append("technical_aborted_rate_limit")
            return candles, True
        except YahooError:
            warnings.append(f"candles_unavailable:{ticker}")
            continue
        _closes_cache[ticker] = (today, series)
        candles[ticker] = series
    return candles, False


async def _fetch_earnings(
    finnhub, tickers: set[str], warnings: list[str]
) -> dict[str, date] | None:
    """Earnings dates in [today, today + lookahead] per ticker.

    None = calendar unavailable (limited/premium on the free tier) — the
    flag degrades, it never fails the endpoint.
    """
    start = today_ny()
    end = start + timedelta(days=EARNINGS_LOOKAHEAD_DAYS)
    try:
        entries = await finnhub.get_earnings_calendar(start, end)
    except FinnhubError:
        warnings.append("earnings_calendar_unavailable")
        return None

    earnings: dict[str, date] = {}
    for entry in entries:
        symbol = (entry.get("symbol") or "").upper()
        raw_date = entry.get("date")
        if symbol not in tickers or not raw_date:
            continue
        try:
            entry_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        # Keep the earliest date if a ticker somehow appears twice.
        if symbol not in earnings or entry_date < earnings[symbol]:
            earnings[symbol] = entry_date
    return earnings


# --- Per-stock assembly --------------------------------------------------------------


def _build_stock(
    ticker: str,
    series: list[Candle] | None,
    earnings: dict[str, date] | None,
    warnings: list[str],
) -> StockTechnical:
    earnings_this_week = None if earnings is None else ticker in earnings
    earnings_date = earnings.get(ticker) if earnings else None

    if not series:
        return StockTechnical(
            ticker=ticker,
            data_status="unavailable",
            close=None, as_of=None,
            high_52w=None, low_52w=None,
            pct_from_high_52w=None, pct_from_low_52w=None,
            ma50=None, ma200=None,
            above_ma50=None, above_ma200=None,
            pct_from_ma50=None, pct_from_ma200=None,
            earnings_this_week=earnings_this_week,
            earnings_date=earnings_date,
            label=None,
        )

    closes = [c.close for c in series]
    # Yahoo closes carry float32 artifacts (745.4000244140625) — store cents.
    close = money(closes[-1])

    high_52w = low_52w = pct_from_high = pct_from_low = None
    ma50 = ma200 = pct_from_ma50 = pct_from_ma200 = None
    above_ma50 = above_ma200 = None
    insufficient = False

    if len(closes) >= HIGH_LOW_WINDOW:
        window = closes[-HIGH_LOW_WINDOW:]
        high_52w, low_52w = money(max(window)), money(min(window))
        pct_from_high = pct_distance(close, high_52w)
        pct_from_low = pct_distance(close, low_52w)
    else:
        insufficient = True

    if len(closes) >= 50:
        ma50 = sma(closes, 50)
        above_ma50 = close > ma50
        pct_from_ma50 = pct_distance(close, ma50)
    else:
        insufficient = True

    if len(closes) >= 200:
        ma200 = sma(closes, 200)
        above_ma200 = close > ma200
        pct_from_ma200 = pct_distance(close, ma200)
    else:
        insufficient = True

    if insufficient:
        warnings.append(f"technical_insufficient_history:{ticker}")

    return StockTechnical(
        ticker=ticker,
        data_status="ok",
        close=close,
        as_of=series[-1].date,
        high_52w=high_52w,
        low_52w=low_52w,
        pct_from_high_52w=pct_from_high,
        pct_from_low_52w=pct_from_low,
        ma50=ma50,
        ma200=ma200,
        above_ma50=above_ma50,
        above_ma200=above_ma200,
        pct_from_ma50=pct_from_ma50,
        pct_from_ma200=pct_from_ma200,
        earnings_this_week=earnings_this_week,
        earnings_date=earnings_date,
        label=classify_technical(above_ma200, pct_from_high, pct_from_low),
    )


async def build_portfolio_technical(
    tickers: list[str], yahoo, finnhub
) -> PortfolioTechnicalResponse:
    """Technical snapshot for the given (unique, sorted) portfolio tickers.

    Raises TechnicalDataUnavailableError when every ticker failed to fetch.
    """
    warnings: list[str] = []
    candles, rate_limited = await fetch_daily_closes_cached(yahoo, tickers, warnings)
    if tickers and not candles:
        raise TechnicalDataUnavailableError(rate_limited=rate_limited)

    earnings = await _fetch_earnings(finnhub, set(tickers), warnings)
    stocks = [
        _build_stock(ticker, candles.get(ticker), earnings, warnings)
        for ticker in tickers
    ]
    return PortfolioTechnicalResponse(
        as_of_date=today_ny(), stocks=stocks, warnings=warnings
    )


# --- Port news ------------------------------------------------------------------------


def to_news_items(raw: list[dict]) -> list[NewsItem]:
    """Map Finnhub company-news dicts to NewsItems: skip headline-less junk,
    newest first, capped at MAX_NEWS_ITEMS."""
    items: list[NewsItem] = []
    for entry in raw:
        headline = (entry.get("headline") or "").strip()
        ts = entry.get("datetime")
        if not headline or not isinstance(ts, (int, float)):
            continue
        items.append(
            NewsItem(
                headline=headline,
                source=entry.get("source") or None,
                url=entry.get("url") or None,
                summary=entry.get("summary") or None,
                published_at=datetime.fromtimestamp(ts, tz=NY_TZ),
            )
        )
    items.sort(key=lambda item: item.published_at, reverse=True)
    return items[:MAX_NEWS_ITEMS]
