import asyncio
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.timeutils import today_ny
from app.models import Position, RealizedTrade
from app.schemas.position import (
    PortfolioResponse,
    PositionCloseRequest,
    PositionCreate,
    PositionResponse,
    PositionWithPnL,
    RealizedTradeResponse,
    RealizedTradesResponse,
)
from app.services import pnl
from app.services.finnhub_client import (
    FinnhubClient,
    FinnhubError,
    FinnhubRateLimitError,
    Quote,
    get_finnhub_client,
)

router = APIRouter(prefix="/positions", tags=["positions"])


@router.post("", response_model=PositionResponse, status_code=201)
async def create_position(
    payload: PositionCreate,
    db: AsyncSession = Depends(get_db),
    finnhub: FinnhubClient = Depends(get_finnhub_client),
) -> Position:
    try:
        is_nasdaq = await finnhub.is_nasdaq_ticker(payload.ticker)
    except FinnhubRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Finnhub rate limit reached — try again in a minute.",
        )
    except FinnhubError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not validate the ticker with Finnhub right now: {exc}",
        )

    if not is_nasdaq:
        raise HTTPException(
            status_code=400,
            detail=f"'{payload.ticker}' was not found as a NASDAQ-listed symbol.",
        )

    position = Position(
        ticker=payload.ticker,
        quantity=payload.quantity,
        purchase_price=payload.purchase_price,
        purchase_date=payload.purchase_date or today_ny(),
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return position


@router.get("", response_model=PortfolioResponse)
async def list_positions(
    db: AsyncSession = Depends(get_db),
    finnhub: FinnhubClient = Depends(get_finnhub_client),
) -> PortfolioResponse:
    positions = (await db.execute(select(Position).order_by(Position.id))).scalars().all()

    # One quote per unique ticker, fetched concurrently. A failed quote must
    # not break the whole portfolio view — that position just has no price.
    tickers = sorted({p.ticker for p in positions})
    results = await asyncio.gather(
        *(finnhub.get_quote(t) for t in tickers), return_exceptions=True
    )
    quotes: dict[str, Quote] = {
        ticker: result
        for ticker, result in zip(tickers, results)
        if isinstance(result, Quote)
    }

    items: list[PositionWithPnL] = []
    total_cost = Decimal("0")
    total_market_value: Decimal | None = None
    total_unrealized: Decimal | None = None

    for position in positions:
        cost_basis = pnl.money(position.purchase_price * position.quantity)
        total_cost += cost_basis
        quote = quotes.get(position.ticker)

        if quote is None:
            current_price = market_value = unrealized = unrealized_pct = None
            status = "unavailable"
        else:
            current_price = quote.current_price
            market_value = pnl.money(current_price * position.quantity)
            unrealized = pnl.unrealized_pnl(
                position.purchase_price, position.quantity, current_price
            )
            unrealized_pct = pnl.unrealized_pnl_pct(position.purchase_price, current_price)
            total_market_value = (total_market_value or Decimal("0")) + market_value
            total_unrealized = (total_unrealized or Decimal("0")) + unrealized
            status = "ok"

        items.append(
            PositionWithPnL(
                id=position.id,
                ticker=position.ticker,
                quantity=position.quantity,
                purchase_price=position.purchase_price,
                purchase_date=position.purchase_date,
                created_at=position.created_at,
                cost_basis=cost_basis,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized,
                unrealized_pnl_pct=unrealized_pct,
                price_status=status,
            )
        )

    return PortfolioResponse(
        positions=items,
        total_cost_basis=total_cost,
        total_market_value=total_market_value,
        total_unrealized_pnl=total_unrealized,
    )


@router.get("/realized", response_model=RealizedTradesResponse)
async def list_realized_trades(db: AsyncSession = Depends(get_db)) -> RealizedTradesResponse:
    trades = (
        (await db.execute(select(RealizedTrade).order_by(RealizedTrade.sale_date.desc(), RealizedTrade.id.desc())))
        .scalars()
        .all()
    )
    total = sum((t.realized_pnl for t in trades), Decimal("0"))
    return RealizedTradesResponse(
        trades=[RealizedTradeResponse.model_validate(t) for t in trades],
        total_realized_pnl=pnl.money(total),
    )


@router.post("/{position_id}/close", response_model=RealizedTradeResponse)
async def close_position(
    position_id: int,
    payload: PositionCloseRequest,
    db: AsyncSession = Depends(get_db),
) -> RealizedTrade:
    position = await db.get(Position, position_id)
    if position is None:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")

    trade = RealizedTrade(
        ticker=position.ticker,
        quantity=position.quantity,
        purchase_price=position.purchase_price,
        sale_price=payload.sale_price,
        sale_date=payload.sale_date or today_ny(),
        realized_pnl=pnl.realized_pnl(
            position.purchase_price, payload.sale_price, position.quantity
        ),
    )
    db.add(trade)
    await db.delete(position)
    await db.commit()
    await db.refresh(trade)
    return trade


@router.delete("/{position_id}", status_code=204)
async def delete_position(position_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Remove a mis-entered position WITHOUT recording a realized trade.

    To close a position properly (and record P&L), use POST /positions/{id}/close.
    """
    position = await db.get(Position, position_id)
    if position is None:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")
    await db.delete(position)
    await db.commit()
