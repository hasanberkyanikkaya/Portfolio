from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Prediction
from app.schemas.predictions import (
    PredictionItem,
    PredictionsRunResponse,
    PredictionsSummaryResponse,
    TickerPredictionsResponse,
)
from app.services.disclaimers import STATISTICAL_DISCLAIMER
from app.services.predictions import (
    ALGORITHM_NAMES,
    PredictionsDataUnavailableError,
    build_algorithm_stats,
    run_prediction_cycle,
)
from app.services.yahoo_client import YahooClient, get_yahoo_client

router = APIRouter(prefix="/predictions", tags=["predictions"])

RECENT_LIMIT = 50
TICKER_LIMIT = 100


def _to_item(p: Prediction) -> PredictionItem:
    return PredictionItem(
        id=p.id,
        ticker=p.ticker,
        algorithm=p.algorithm,
        algorithm_name=ALGORITHM_NAMES[p.algorithm],
        prediction_date=p.prediction_date,
        predicted_direction=p.predicted_direction,
        price_at_prediction=p.price_at_prediction,
        horizon_days=p.horizon_days,
        status=p.status,
        evaluation_date=p.evaluation_date,
        price_at_evaluation=p.price_at_evaluation,
        actual_return_pct=p.actual_return_pct,
        created_at=p.created_at,
    )


@router.get("", response_model=PredictionsSummaryResponse)
async def predictions_summary(db: AsyncSession = Depends(get_db)) -> PredictionsSummaryResponse:
    """All-ticker track record. DB only — never calls external APIs.

    An empty DB is a normal pre-first-run state, not a 404.
    """
    all_rows = (await db.execute(select(Prediction))).scalars().all()
    recent = sorted(
        all_rows, key=lambda p: (p.prediction_date, p.id), reverse=True
    )[:RECENT_LIMIT]
    return PredictionsSummaryResponse(
        stats=build_algorithm_stats(all_rows),
        predictions=[_to_item(p) for p in recent],
        disclaimer=STATISTICAL_DISCLAIMER,
    )


# NOTE: the literal /run route must be registered before /{ticker}.
@router.post("/run", response_model=PredictionsRunResponse)
async def run_predictions(
    db: AsyncSession = Depends(get_db),
    yahoo: YahooClient = Depends(get_yahoo_client),
) -> PredictionsRunResponse:
    """Manual trigger: evaluate pending predictions, then log today's new ones."""
    try:
        created, evaluated, expired, warnings = await run_prediction_cycle(db, yahoo)
    except PredictionsDataUnavailableError as exc:
        if exc.rate_limited:
            raise HTTPException(
                status_code=429,
                detail="Yahoo rate limit reached — try again in a few minutes.",
            )
        raise HTTPException(
            status_code=503,
            detail="No historical data available for any portfolio ticker right now.",
        )
    return PredictionsRunResponse(
        created=created,
        evaluated=evaluated,
        expired=expired,
        warnings=warnings,
        disclaimer=STATISTICAL_DISCLAIMER,
    )


@router.get("/{ticker}", response_model=TickerPredictionsResponse)
async def ticker_predictions(
    ticker: str, db: AsyncSession = Depends(get_db)
) -> TickerPredictionsResponse:
    """One ticker's full track record. DB only."""
    symbol = ticker.upper()
    rows = (
        (await db.execute(select(Prediction).where(Prediction.ticker == symbol)))
        .scalars()
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=404, detail=f"No predictions recorded for {symbol}."
        )
    recent = sorted(rows, key=lambda p: (p.prediction_date, p.id), reverse=True)[:TICKER_LIMIT]
    return TickerPredictionsResponse(
        ticker=symbol,
        stats=build_algorithm_stats(rows),
        predictions=[_to_item(p) for p in recent],
        disclaimer=STATISTICAL_DISCLAIMER,
    )
