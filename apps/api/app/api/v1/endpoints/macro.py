"""
/api/v1/macro — the Macro Regime Engine's read endpoint.

This computes the snapshot fresh from currently-ingested data on every
request (no caching yet — this is Stage 3's first slice; a scheduled
snapshot-and-store job can be added later if computing this on every
request ever becomes a real cost).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.go_os.macro.calculations import (
    EmploymentCondition,
    GoldBias,
    InflationLevel,
    MacroRegime,
    PolicyStance,
    RealYieldLevel,
    Trend,
)
from app.go_os.macro.repository import SeriesNotIngestedError
from app.go_os.macro.service import compute_macro_regime_snapshot

router = APIRouter(prefix="/macro", tags=["macro"])


class GoldScoreResponse(BaseModel):
    real_yield_contribution: int
    inflation_contribution: int
    policy_contribution: int
    total: int
    bias: GoldBias


class MacroRegimeResponse(BaseModel):
    as_of: date

    inflation_yoy_pct: float
    inflation_level: InflationLevel
    inflation_trend: Trend

    unemployment_rate_pct: float
    employment_condition: EmploymentCondition

    fed_funds_rate_pct: float
    policy_stance: PolicyStance

    real_yield_proxy_pct: float
    real_yield_level: RealYieldLevel
    real_yield_caveat: str

    regime: MacroRegime
    gold_score: GoldScoreResponse


@router.get("/regime", response_model=MacroRegimeResponse)
def get_macro_regime(db: Session = Depends(get_db)) -> MacroRegimeResponse:
    try:
        snapshot = compute_macro_regime_snapshot(db)
    except SeriesNotIngestedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MacroRegimeResponse(
        as_of=snapshot.as_of,
        inflation_yoy_pct=snapshot.inflation_yoy_pct,
        inflation_level=snapshot.inflation_level,
        inflation_trend=snapshot.inflation_trend,
        unemployment_rate_pct=snapshot.unemployment_rate_pct,
        employment_condition=snapshot.employment_condition,
        fed_funds_rate_pct=snapshot.fed_funds_rate_pct,
        policy_stance=snapshot.policy_stance,
        real_yield_proxy_pct=snapshot.real_yield_proxy_pct,
        real_yield_level=snapshot.real_yield_level,
        real_yield_caveat=snapshot.real_yield_caveat,
        regime=snapshot.regime,
        gold_score=GoldScoreResponse(
            real_yield_contribution=snapshot.gold_score.real_yield_contribution,
            inflation_contribution=snapshot.gold_score.inflation_contribution,
            policy_contribution=snapshot.gold_score.policy_contribution,
            total=snapshot.gold_score.total,
            bias=snapshot.gold_score.bias,
        ),
    )
