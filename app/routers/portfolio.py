from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.timeutils import today_ny
from app.models import DailyReport, Position
from app.schemas.portfolio import PortfolioTechnicalResponse, TickerNewsResponse
from app.schemas.protect import ProtectContent, ProtectOut
from app.schemas.setups import SetupsContent, SetupsOut
from app.services.claude_client import (
    ClaudeClient,
    ClaudeError,
    ClaudeRateLimitError,
    get_claude_client,
)
from app.services.finnhub_client import (
    FinnhubClient,
    FinnhubError,
    FinnhubRateLimitError,
    get_finnhub_client,
)
from app.services.protect import (
    REPORT_PROTECT,
    ProtectDataUnavailableError,
    generate_protect,
)
from app.services.setups import (
    REPORT_SETUPS,
    SetupsDataUnavailableError,
    generate_setups,
)
from app.services.technical import (
    NEWS_LOOKBACK_DAYS,
    TechnicalDataUnavailableError,
    build_portfolio_technical,
    to_news_items,
)
from app.services.yahoo_client import YahooClient, get_yahoo_client

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/technical", response_model=PortfolioTechnicalResponse)
async def portfolio_technical(
    db: AsyncSession = Depends(get_db),
    yahoo: YahooClient = Depends(get_yahoo_client),
    finnhub: FinnhubClient = Depends(get_finnhub_client),
) -> PortfolioTechnicalResponse:
    positions = (await db.execute(select(Position).order_by(Position.id))).scalars().all()
    tickers = sorted({p.ticker for p in positions})
    if not tickers:
        return PortfolioTechnicalResponse(as_of_date=today_ny(), stocks=[], warnings=[])

    try:
        return await build_portfolio_technical(tickers, yahoo, finnhub)
    except TechnicalDataUnavailableError as exc:
        if exc.rate_limited:
            raise HTTPException(
                status_code=429,
                detail="Yahoo rate limit reached — try again in a few minutes.",
            )
        raise HTTPException(
            status_code=503,
            detail="No historical data available for any portfolio ticker right now.",
        )


# --- Setups (cached daily report) -----------------------------------------------


def _setups_out(report: DailyReport) -> SetupsOut:
    return SetupsOut(
        report_date=report.report_date,
        content=SetupsContent.model_validate_json(report.content),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("/setups", response_model=SetupsOut)
async def latest_setups(db: AsyncSession = Depends(get_db)) -> SetupsOut:
    """Latest cached Setups report. DB only — never calls Yahoo/Claude."""
    result = await db.execute(
        select(DailyReport)
        .where(DailyReport.report_type == REPORT_SETUPS)
        .order_by(DailyReport.report_date.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No Setups report has been generated yet. "
            "Use POST /portfolio/setups/refresh to create one.",
        )
    return _setups_out(report)


@router.post("/setups/refresh", response_model=SetupsOut)
async def refresh_setups(
    db: AsyncSession = Depends(get_db),
    yahoo: YahooClient = Depends(get_yahoo_client),
    claude: ClaudeClient = Depends(get_claude_client),
) -> SetupsOut:
    """Regenerate today's Setups report even if already cached.

    An empty setups list is a valid result; only a total Yahoo blackout or a
    Claude failure maps to an HTTP error.
    """
    try:
        report = await generate_setups(db, yahoo, claude, force=True)
    except SetupsDataUnavailableError as exc:
        if exc.rate_limited:
            raise HTTPException(
                status_code=429,
                detail="Yahoo rate limit reached — try again in a few minutes.",
            )
        raise HTTPException(
            status_code=503,
            detail="No historical data available for any portfolio ticker right now.",
        )
    except ClaudeRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Anthropic rate limit reached — try again in a minute.",
        )
    except ClaudeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not generate the Setups report right now: {exc}",
        )
    return _setups_out(report)


# --- Protect (cached daily report) ------------------------------------------------


def _protect_out(report: DailyReport) -> ProtectOut:
    return ProtectOut(
        report_date=report.report_date,
        content=ProtectContent.model_validate_json(report.content),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("/protect", response_model=ProtectOut)
async def latest_protect(db: AsyncSession = Depends(get_db)) -> ProtectOut:
    """Latest cached Protect report. DB only — never calls Finnhub/Claude."""
    result = await db.execute(
        select(DailyReport)
        .where(DailyReport.report_type == REPORT_PROTECT)
        .order_by(DailyReport.report_date.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No Protect report has been generated yet. "
            "Use POST /portfolio/protect/refresh to create one.",
        )
    return _protect_out(report)


@router.post("/protect/refresh", response_model=ProtectOut)
async def refresh_protect(
    db: AsyncSession = Depends(get_db),
    finnhub: FinnhubClient = Depends(get_finnhub_client),
    claude: ClaudeClient = Depends(get_claude_client),
) -> ProtectOut:
    """Regenerate today's Protect report even if already cached.

    Quote/profile/calendar failures degrade into `warnings`; an empty
    portfolio is a valid report. Only a Claude failure (or the defensive
    no-value case) maps to an HTTP error.
    """
    try:
        report = await generate_protect(db, finnhub, claude, force=True)
    except ProtectDataUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="Portfolio value could not be computed right now — try again later.",
        )
    except FinnhubRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Finnhub rate limit reached — try again in a minute.",
        )
    except ClaudeRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Anthropic rate limit reached — try again in a minute.",
        )
    except ClaudeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not generate the Protect report right now: {exc}",
        )
    return _protect_out(report)


# --- Per-ticker news (keep LAST — path-param route) --------------------------------


@router.get("/{ticker}/news", response_model=TickerNewsResponse)
async def ticker_news(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    finnhub: FinnhubClient = Depends(get_finnhub_client),
) -> TickerNewsResponse:
    symbol = ticker.strip().upper()
    in_portfolio = (
        await db.execute(select(Position.id).where(Position.ticker == symbol).limit(1))
    ).first()
    if in_portfolio is None:
        raise HTTPException(
            status_code=404, detail=f"'{symbol}' is not in the portfolio."
        )

    to_date = today_ny()
    from_date = to_date - timedelta(days=NEWS_LOOKBACK_DAYS)
    try:
        raw = await finnhub.get_company_news(symbol, from_date, to_date)
    except FinnhubRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Finnhub rate limit reached — try again in a minute.",
        )
    except FinnhubError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not fetch news from Finnhub right now: {exc}",
        )

    return TickerNewsResponse(
        ticker=symbol,
        from_date=from_date,
        to_date=to_date,
        items=to_news_items(raw),
    )
