from datetime import date, datetime
from zoneinfo import ZoneInfo

# All date/time logic in this project uses New York time as the reference.
NY_TZ = ZoneInfo("America/New_York")


def today_ny() -> date:
    return datetime.now(NY_TZ).date()
