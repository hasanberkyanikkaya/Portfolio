from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

PredictionAlgorithm = Literal["trend_ma", "rsi_reversion", "swing_breakout"]
PredictionDirection = Literal["up", "down"]
PredictionStatus = Literal["pending", "correct", "incorrect", "expired"]


class PredictionItem(BaseModel):
    id: int
    ticker: str
    algorithm: PredictionAlgorithm
    algorithm_name: str  # Turkish display name (ALGORITHM_NAMES in services/predictions.py)
    prediction_date: date  # date of the last Yahoo candle the algorithm saw
    predicted_direction: PredictionDirection
    price_at_prediction: Decimal
    horizon_days: int
    status: PredictionStatus
    evaluation_date: date | None
    price_at_evaluation: Decimal | None
    actual_return_pct: Decimal | None
    created_at: datetime


class AlgorithmStats(BaseModel):
    algorithm: PredictionAlgorithm
    algorithm_name: str
    total: int
    correct: int
    incorrect: int
    pending: int
    expired: int
    # correct / (correct + incorrect) * 100; None when nothing decided yet —
    # never a fake 0%.
    accuracy_pct: Decimal | None


class PredictionsSummaryResponse(BaseModel):
    stats: list[AlgorithmStats]
    predictions: list[PredictionItem]  # most recent first
    disclaimer: str


class TickerPredictionsResponse(BaseModel):
    ticker: str
    stats: list[AlgorithmStats]
    predictions: list[PredictionItem]  # most recent first
    disclaimer: str


class PredictionsRunResponse(BaseModel):
    created: int
    evaluated: int
    expired: int
    warnings: list[str]
    disclaimer: str
