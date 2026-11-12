"""Static editorial macro-event calendar (Phase 7, Protect report).

Finnhub's economic calendar is premium (403 on the free tier), so the key US
macro events come from this git-maintained module — same editorial-data
precedent as glossary.py and SENTIMENT_BASKET:

- FOMC:  the Fed's published 2026 meeting schedule (decision days, exact).
- CPI:   approximate mid-month BLS release dates (approximate=True — the BLS
         schedule shifts by a day or two; good enough for "this week" framing).
- NFP:   nonfarm payrolls = first Friday of the month, computed (no list).

`static_events` is pure (start date in, events out) so tests never monkeypatch
today_ny. `finnhub_events` additionally asks Finnhub for high-impact US events
and merges them as event_type "other" — on the free tier that call 403s and
degrades to a `economic_calendar_unavailable` warning, which is the normal
case. Entries that duplicate the static event types (CPI/FOMC/NFP keywords)
are dropped.

Which sectors react to which event type is editorial too
(EVENT_SECTOR_SENSITIVITY): lowercase keywords matched against each holding's
`finnhubIndustry` by containment. Update both tables in git when the year
rolls over or conventions change.
"""

from datetime import date, timedelta

from app.schemas.protect import MacroEvent
from app.services.finnhub_client import FinnhubError

MACRO_LOOKAHEAD_DAYS = 7
MAX_FINNHUB_EVENTS = 8

# Fed-published 2026 FOMC decision days (second day of each two-day meeting).
FOMC_DECISION_DATES_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
]

# Approximate BLS CPI release days (typically 08:30 ET, ~2nd week of month).
CPI_RELEASE_DATES_2026 = [
    date(2026, 1, 13),
    date(2026, 2, 11),
    date(2026, 3, 11),
    date(2026, 4, 10),
    date(2026, 5, 12),
    date(2026, 6, 10),
    date(2026, 7, 14),
    date(2026, 8, 12),
    date(2026, 9, 11),
    date(2026, 10, 13),
    date(2026, 11, 10),
    date(2026, 12, 10),
]

# Keywords (lowercase, containment) matched against finnhubIndustry values.
EVENT_SECTOR_SENSITIVITY: dict[str, list[str]] = {
    # Rate/duration-sensitive: high-growth tech and leveraged/rate businesses.
    "FOMC": [
        "technology", "semiconductor", "software", "internet", "media",
        "real estate", "bank", "financial", "biotech", "pharmaceutical",
    ],
    # Inflation prints move the same rate-expectation channel.
    "CPI": [
        "technology", "semiconductor", "software", "internet", "media",
        "real estate", "bank", "financial", "biotech", "pharmaceutical",
    ],
    # Labor-market prints hit cyclical/consumer demand first.
    "NFP": [
        "consumer", "retail", "restaurant", "hotel", "industrial",
        "transportation", "airline", "leisure",
    ],
    "other": [],
}

# Static event names that a Finnhub entry may duplicate.
_STATIC_KEYWORDS = ("cpi", "consumer price", "fomc", "interest rate", "nonfarm")


def first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def _in_window(day: date, start: date, end: date) -> bool:
    return start <= day <= end


def static_events(start: date, days: int = MACRO_LOOKAHEAD_DAYS) -> list[MacroEvent]:
    """Key US macro events in [start, start + days], from the static tables."""
    end = start + timedelta(days=days)
    events = [
        MacroEvent(
            date=d, event_type="FOMC", title="FOMC faiz kararı",
            approximate=False, source="static",
        )
        for d in FOMC_DECISION_DATES_2026
        if _in_window(d, start, end)
    ]
    events += [
        MacroEvent(
            date=d, event_type="CPI", title="CPI (enflasyon) verisi",
            approximate=True, source="static",
        )
        for d in CPI_RELEASE_DATES_2026
        if _in_window(d, start, end)
    ]
    # NFP: check the first Friday of every month the window touches.
    seen_months = {(start.year, start.month), (end.year, end.month)}
    events += [
        MacroEvent(
            date=nfp, event_type="NFP", title="Tarım dışı istihdam (NFP)",
            approximate=False, source="static",
        )
        for year, month in sorted(seen_months)
        if _in_window(nfp := first_friday(year, month), start, end)
    ]
    events.sort(key=lambda e: e.date)
    return events


async def finnhub_events(
    finnhub, start: date, end: date, warnings: list[str]
) -> list[MacroEvent]:
    """High-impact US events from Finnhub's economic calendar (premium — the
    free-tier 403 degrades to a warning and the static events stand alone)."""
    try:
        entries = await finnhub.get_economic_calendar(start, end)
    except FinnhubError:
        warnings.append("economic_calendar_unavailable")
        return []

    events: list[MacroEvent] = []
    for entry in entries:
        if (entry.get("country") or "").upper() != "US":
            continue
        if (entry.get("impact") or "").lower() != "high":
            continue
        title = (entry.get("event") or "").strip()
        if not title or any(k in title.lower() for k in _STATIC_KEYWORDS):
            continue  # blank or duplicates a static event type
        raw = (entry.get("time") or entry.get("date") or "")[:10]
        try:
            event_date = date.fromisoformat(raw)
        except ValueError:
            continue
        if not _in_window(event_date, start, end):
            continue
        events.append(
            MacroEvent(
                date=event_date, event_type="other", title=title,
                approximate=False, source="finnhub",
            )
        )
        if len(events) >= MAX_FINNHUB_EVENTS:
            break
    return events
