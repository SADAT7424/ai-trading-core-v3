"""
/api/v1/market/state — Market Core's read endpoint. Computes trend,
momentum, volatility, RSI, and regime fresh from currently-ingested bars on
every request (same no-caching approach as /api/v1/macro/regime for now).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.market_core.calculations import (
    MarketRegime,
    Momentum,
    RsiCondition,
    Trend,
    VolatilityLevel,
)
from app.market_core.repository import NoMarketDataError
from app.market_core.service import compute_market_state

router = APIRouter(prefix="/market/state", tags=["market"])


class MarketStateResponse(BaseModel):
    symbol: str
    interval: str
    as_of: datetime
    latest_close: float

    sma_fast: float
    sma_slow: float
    trend: Trend

    roc_pct: float
    momentum: Momentum

    atr: float
    atr_pct_of_price: float
    volatility: VolatilityLevel

    rsi: float
    rsi_condition: RsiCondition

    regime: MarketRegime


@router.get("/{symbol}", response_model=MarketStateResponse)
def get_market_state(
    symbol: str, interval: str = "1day", db: Session = Depends(get_db)
) -> MarketStateResponse:
    try:
        snapshot = compute_market_state(db, symbol, interval)
    except NoMarketDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MarketStateResponse(
        symbol=snapshot.symbol,
        interval=snapshot.interval,
        as_of=snapshot.as_of,
        latest_close=snapshot.latest_close,
        sma_fast=snapshot.sma_fast,
        sma_slow=snapshot.sma_slow,
        trend=snapshot.trend,
        roc_pct=snapshot.roc_pct,
        momentum=snapshot.momentum,
        atr=snapshot.atr,
        atr_pct_of_price=snapshot.atr_pct_of_price,
        volatility=snapshot.volatility,
        rsi=snapshot.rsi,
        rsi_condition=snapshot.rsi_condition,
        regime=snapshot.regime,
    )
