"""
/api/v1/execution — paper order submission and order history.

Every response is explicit about `broker: "PAPER"` so it is never
ambiguous that this is simulated execution, not a real trade.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.execution.paper_broker import NoPriceDataError
from app.execution.service import submit_paper_order
from app.go_os.macro.repository import SeriesNotIngestedError
from app.market_core.repository import NoMarketDataError
from app.models.execution import Order
from app.trading_core.service import UnsupportedSymbolError

router = APIRouter(prefix="/execution", tags=["execution"])


class OrderResponse(BaseModel):
    id: str
    symbol: str
    direction: str
    status: str
    broker: str
    requested_price: float
    filled_price: float | None
    stop_price: float
    units: float
    risk_amount: float
    risk_pct: float
    quality_grade: str | None
    classification: str | None
    rejection_reasons: str | None
    created_at: datetime
    filled_at: datetime | None


def _to_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        symbol=order.symbol,
        direction=order.direction,
        status=order.status,
        broker=order.broker,
        requested_price=float(order.requested_price),
        filled_price=float(order.filled_price) if order.filled_price is not None else None,
        stop_price=float(order.stop_price),
        units=float(order.units),
        risk_amount=float(order.risk_amount),
        risk_pct=float(order.risk_pct),
        quality_grade=order.quality_grade,
        classification=order.classification,
        rejection_reasons=order.rejection_reasons,
        created_at=order.created_at,
        filled_at=order.filled_at,
    )


@router.post("/orders/{symbol}", response_model=OrderResponse)
def submit_order(
    symbol: str,
    interval: str = "1day",
    proposed_risk_pct: float | None = None,
    open_positions_count: int = 0,
    open_portfolio_heat_pct: float = 0.0,
    db: Session = Depends(get_db),
) -> OrderResponse:
    try:
        order = submit_paper_order(
            db,
            symbol,
            interval,
            proposed_risk_pct=proposed_risk_pct,
            open_positions_count=open_positions_count,
            open_portfolio_heat_pct=open_portfolio_heat_pct,
        )
    except (
        UnsupportedSymbolError,
        SeriesNotIngestedError,
        NoMarketDataError,
        NoPriceDataError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _to_response(order)


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(
    symbol: str | None = None, limit: int = 50, db: Session = Depends(get_db)
) -> list[OrderResponse]:
    query = select(Order).order_by(Order.created_at.desc()).limit(limit)
    if symbol is not None:
        query = query.where(Order.symbol == symbol)
    orders = db.execute(query).scalars().all()
    return [_to_response(o) for o in orders]
