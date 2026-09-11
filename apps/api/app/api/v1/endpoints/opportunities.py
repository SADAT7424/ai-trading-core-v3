"""
/api/v1/opportunities — Trading Core's read endpoint. Computes fresh from
current macro + market data on every request, same approach as the two
engines it depends on.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.go_os.macro.repository import SeriesNotIngestedError
from app.market_core.repository import NoMarketDataError
from app.trading_core.calculations import Direction, QualityGrade, TradeClassification
from app.trading_core.service import UnsupportedSymbolError, compute_opportunity

router = APIRouter(prefix="/opportunities", tags=["trading_core"])


class SetupResponse(BaseModel):
    direction: Direction
    distance_to_fast_sma_pct: float
    technical_score: float


class ScoreResponse(BaseModel):
    technical_score: float
    macro_alignment_score: float
    overall_score: float
    quality: QualityGrade


class OpportunityResponse(BaseModel):
    symbol: str
    interval: str
    as_of: datetime
    latest_close: float
    setup: SetupResponse
    classification: TradeClassification
    gold_macro_score: int
    score: ScoreResponse | None


@router.get("/{symbol}", response_model=OpportunityResponse)
def get_opportunity(
    symbol: str, interval: str = "1day", db: Session = Depends(get_db)
) -> OpportunityResponse:
    try:
        snapshot = compute_opportunity(db, symbol, interval)
    except (UnsupportedSymbolError, SeriesNotIngestedError, NoMarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return OpportunityResponse(
        symbol=snapshot.symbol,
        interval=snapshot.interval,
        as_of=snapshot.as_of,
        latest_close=snapshot.latest_close,
        setup=SetupResponse(
            direction=snapshot.setup.direction,
            distance_to_fast_sma_pct=snapshot.setup.distance_to_fast_sma_pct,
            technical_score=snapshot.setup.technical_score,
        ),
        classification=snapshot.classification,
        gold_macro_score=snapshot.gold_macro_score,
        score=(
            ScoreResponse(
                technical_score=snapshot.score.technical_score,
                macro_alignment_score=snapshot.score.macro_alignment_score,
                overall_score=snapshot.score.overall_score,
                quality=snapshot.score.quality,
            )
            if snapshot.score is not None
            else None
        ),
    )
