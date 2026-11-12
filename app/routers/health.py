from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"

    payload = HealthResponse(status="ok", database=database)
    status_code = 200 if database == "ok" else 503
    return JSONResponse(status_code=status_code, content=payload.model_dump())
