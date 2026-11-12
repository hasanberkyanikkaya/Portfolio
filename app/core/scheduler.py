"""APScheduler setup for the seven daily jobs.

Timing (America/New_York, DST handled by zoneinfo):
- premarket_report: 09:20 ET mon-fri (10 min before the 09:30 NASDAQ open)
- close_report:     16:45 ET mon-fri (45 min after the 16:00 close, so data settles)
- market_pulse:     16:50 ET mon-fri (5 min after the close report — decouples
  failures and spreads the Finnhub calls away from the 16:45 burst)
- sentiment_report: 16:55 ET mon-fri (5 min after Market Pulse — keeps its ~32
  sequential Yahoo fetches away from Market Pulse's 15)
- setups_report:    17:00 ET mon-fri (its per-holding Yahoo fetches reuse the
  technical memo cache and stay clear of the sentiment basket run)
- protect_report:   17:05 ET mon-fri (Finnhub quotes/profiles + static macro
  calendar — no Yahoo at all)
- predictions:      17:10 ET mon-fri (evaluate pending predictions + log new
  ones; its Yahoo fetches reuse the technical memo cache warmed by the 17:00
  setups run, so portfolio tickers cost zero extra fetches)

Known limitation: no US-market-holiday awareness — on a holiday the job still
runs and the report simply reflects quiet data.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.timeutils import NY_TZ
from app.services.market_pulse import run_market_pulse_job
from app.services.predictions import run_predictions_job
from app.services.protect import run_protect_job
from app.services.reports import run_close_job, run_premarket_job
from app.services.sentiment import run_sentiment_job
from app.services.setups import run_setups_job

logger = logging.getLogger(__name__)

JOB_DEFAULTS = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 3600}


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=NY_TZ, job_defaults=JOB_DEFAULTS)
    scheduler.add_job(
        run_premarket_job,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=20, timezone=NY_TZ),
        id="premarket_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_close_job,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=45, timezone=NY_TZ),
        id="close_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_market_pulse_job,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=50, timezone=NY_TZ),
        id="market_pulse",
        replace_existing=True,
    )
    scheduler.add_job(
        run_sentiment_job,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=55, timezone=NY_TZ),
        id="sentiment_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_setups_job,
        CronTrigger(day_of_week="mon-fri", hour=17, minute=0, timezone=NY_TZ),
        id="setups_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_protect_job,
        CronTrigger(day_of_week="mon-fri", hour=17, minute=5, timezone=NY_TZ),
        id="protect_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_predictions_job,
        CronTrigger(day_of_week="mon-fri", hour=17, minute=10, timezone=NY_TZ),
        id="predictions",
        replace_existing=True,
    )
    return scheduler


def log_next_runs(scheduler: AsyncIOScheduler) -> None:
    for job in scheduler.get_jobs():
        logger.info("Scheduled job %s — next run: %s", job.id, job.next_run_time)
