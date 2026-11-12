from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.scheduler import create_scheduler, log_next_runs
from app.routers import (
    glossary,
    health,
    market_pulse,
    portfolio,
    positions,
    predictions,
    reports,
    risk_profile,
    sentiment,
    themes,
)
from app.services.claude_client import close_claude_client
from app.services.finnhub_client import close_finnhub_client
from app.services.yahoo_client import close_yahoo_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tests use httpx.ASGITransport, which never runs lifespan — the scheduler
    # is inert under pytest by construction.
    scheduler = None
    if get_settings().scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
        log_next_runs(scheduler)
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await close_finnhub_client()
    await close_claude_client()
    await close_yahoo_client()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)

app.include_router(health.router)
app.include_router(positions.router)
app.include_router(portfolio.router)
app.include_router(reports.router)
app.include_router(market_pulse.router)
app.include_router(sentiment.router)
app.include_router(glossary.router)
app.include_router(predictions.router)
app.include_router(risk_profile.router)
app.include_router(themes.router)
