"""
/api/v1/risk — configuration, kill switch, and trade evaluation endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.go_os.macro.repository import SeriesNotIngestedError
from app.market_core.repository import NoMarketDataError
from app.models.risk import KillSwitchStateName
from app.models.risk import RiskConfig as RiskConfigModel
from app.risk.calculations import RejectionReason
from app.risk.repository import (
    get_current_kill_switch_state,
    get_or_create_risk_config,
    record_kill_switch_event,
    update_risk_config,
)
from app.risk.service import evaluate_trade_for_symbol
from app.trading_core.calculations import Direction, QualityGrade
from app.trading_core.service import UnsupportedSymbolError

router = APIRouter(prefix="/risk", tags=["risk"])


# --- Config -----------------------------------------------------------------


class RiskConfigResponse(BaseModel):
    account_balance: float
    max_risk_per_trade_pct: float
    max_portfolio_heat_pct: float
    max_open_positions: int
    max_single_asset_exposure_pct: float
    min_quality_grade: QualityGrade


class RiskConfigUpdate(BaseModel):
    account_balance: float | None = Field(default=None, gt=0)
    max_risk_per_trade_pct: float | None = Field(default=None, gt=0, le=100)
    max_portfolio_heat_pct: float | None = Field(default=None, gt=0, le=100)
    max_open_positions: int | None = Field(default=None, gt=0)
    max_single_asset_exposure_pct: float | None = Field(default=None, gt=0, le=100)
    min_quality_grade: QualityGrade | None = None


def _config_to_response(config: RiskConfigModel) -> RiskConfigResponse:
    return RiskConfigResponse(
        account_balance=float(config.account_balance),
        max_risk_per_trade_pct=float(config.max_risk_per_trade_pct),
        max_portfolio_heat_pct=float(config.max_portfolio_heat_pct),
        max_open_positions=config.max_open_positions,
        max_single_asset_exposure_pct=float(config.max_single_asset_exposure_pct),
        min_quality_grade=QualityGrade(config.min_quality_grade),
    )


@router.get("/config", response_model=RiskConfigResponse)
def get_risk_config(db: Session = Depends(get_db)) -> RiskConfigResponse:
    return _config_to_response(get_or_create_risk_config(db))


@router.put("/config", response_model=RiskConfigResponse)
def put_risk_config(
    update: RiskConfigUpdate, db: Session = Depends(get_db)
) -> RiskConfigResponse:
    values = update.model_dump(exclude_none=True)
    if "min_quality_grade" in values:
        values["min_quality_grade"] = values["min_quality_grade"].value
    config = update_risk_config(db, **values)
    return _config_to_response(config)


# --- Kill switch --------------------------------------------------------------


class KillSwitchResponse(BaseModel):
    state: KillSwitchStateName


class KillSwitchUpdate(BaseModel):
    state: KillSwitchStateName
    reason: str = Field(min_length=1, max_length=500)


@router.get("/kill-switch", response_model=KillSwitchResponse)
def get_kill_switch(db: Session = Depends(get_db)) -> KillSwitchResponse:
    return KillSwitchResponse(state=get_current_kill_switch_state(db))


@router.post("/kill-switch", response_model=KillSwitchResponse)
def set_kill_switch(update: KillSwitchUpdate, db: Session = Depends(get_db)) -> KillSwitchResponse:
    event = record_kill_switch_event(db, update.state, update.reason)
    return KillSwitchResponse(state=KillSwitchStateName(event.state))


# --- Trade evaluation -----------------------------------------------------


class PositionResponse(BaseModel):
    risk_pct: float
    risk_amount: float
    units: float
    exposure_pct: float


class TradeEvaluationResponse(BaseModel):
    symbol: str
    direction: Direction
    entry_price: float
    stop_price: float | None
    quality: QualityGrade | None
    kill_switch_state: KillSwitchStateName
    approved: bool
    reasons: list[RejectionReason]
    notes: list[str]
    position: PositionResponse | None


@router.post("/evaluate-trade/{symbol}", response_model=TradeEvaluationResponse)
def evaluate_trade(
    symbol: str,
    interval: str = "1day",
    proposed_risk_pct: float | None = None,
    open_positions_count: int = 0,
    open_portfolio_heat_pct: float = 0.0,
    db: Session = Depends(get_db),
) -> TradeEvaluationResponse:
    try:
        evaluation = evaluate_trade_for_symbol(
            db,
            symbol,
            interval,
            proposed_risk_pct=proposed_risk_pct,
            open_positions_count=open_positions_count,
            open_portfolio_heat_pct=open_portfolio_heat_pct,
        )
    except (UnsupportedSymbolError, SeriesNotIngestedError, NoMarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TradeEvaluationResponse(
        symbol=evaluation.symbol,
        direction=evaluation.direction,
        entry_price=evaluation.entry_price,
        stop_price=evaluation.stop_price,
        quality=evaluation.quality,
        kill_switch_state=evaluation.kill_switch_state,
        approved=evaluation.decision.approved,
        reasons=evaluation.decision.reasons,
        notes=evaluation.decision.notes,
        position=(
            PositionResponse(
                risk_pct=evaluation.decision.position.risk_pct,
                risk_amount=evaluation.decision.position.risk_amount,
                units=evaluation.decision.position.units,
                exposure_pct=evaluation.decision.position.exposure_pct,
            )
            if evaluation.decision.position is not None
            else None
        ),
    )
