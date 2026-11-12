from fastapi import APIRouter, Depends, HTTPException

from app.schemas.themes import ThemeDetailResponse, ThemesListResponse
from app.services.disclaimers import STATISTICAL_DISCLAIMER
from app.services.finnhub_client import FinnhubClient, get_finnhub_client
from app.services.themes import build_theme_detail, get_theme, theme_summaries

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("", response_model=ThemesListResponse)
async def list_themes() -> ThemesListResponse:
    """Curated static theme list — no DB, no external APIs."""
    return ThemesListResponse(themes=theme_summaries(), disclaimer=STATISTICAL_DISCLAIMER)


@router.get("/{slug}", response_model=ThemeDetailResponse)
async def theme_detail(
    slug: str, finnhub: FinnhubClient = Depends(get_finnhub_client)
) -> ThemeDetailResponse:
    """Theme tickers enriched with live Finnhub quotes + industry labels.

    Data failures degrade into `warnings` — even a total Finnhub blackout
    still returns the curated list itself.
    """
    theme = get_theme(slug)
    if theme is None:
        raise HTTPException(status_code=404, detail=f"Unknown theme: {slug}")
    return await build_theme_detail(theme, finnhub)
