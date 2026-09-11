"""
/api/v1/positions — open position listing and monitoring.

Monitoring is a POST (not GET) because it can have a side effect: a
position that no longer passes its exit checks gets closed as part of the
call. This is intentional — see app/positions/service.py.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.go_os.macro.repository import SeriesNotIngestedError
from app.market_core.repository import NoMarketDataError
from app.models.position import Position
from app.positions.calculations import ExitAction, ExitReason, ThesisHealthStatus
from app.positions.repository import get_open_positions, get_position
from app.positions.service import monitor_all_open_positions, monitor_position

router = APIRouter(prefix="/positions", tags=["positions"])


class PositionResponse(BaseModel):
    id: str
    symbol: str
    direction: str
    status: str
    entry_price: float
    initial_stop_price: float
    current_stop_price: float
    target_price: float
    units: float
    entry_classification: str | None
    entry_quality_grade: str | None
    entry_gold_macro_score: int | None
    entry_thesis: str
    close_price: float | None
    close_reason: str | None
    realized_pnl: float | None
    opened_at: datetime
    closed_at: datetime | None


class MonitorResponse(BaseModel):
    position: PositionResponse
    current_price: float
    thesis_health_score: int
    thesis_health_status: ThesisHealthStatus
    thesis_reasons: list[str]
    exit_action: ExitAction
    exit_reason: ExitReason
    notes: list[str]


def _to_response(position: Position) -> PositionResponse:
    return PositionResponse(
        id=position.id,
        symbol=position.symbol,
        direction=position.direction,
        status=position.status,
        entry_price=float(position.entry_price),
        initial_stop_price=float(position.initial_stop_price),
        current_stop_price=float(position.current_stop_price),
        target_price=float(position.target_price),
        units=float(position.units),
        entry_classification=position.entry_classification,
        entry_quality_grade=position.entry_quality_grade,
        entry_gold_macro_score=position.entry_gold_macro_score,
        entry_thesis=position.entry_thesis,
        close_price=float(position.close_price) if position.close_price is not None else None,
        close_reason=position.close_reason,
        realized_pnl=float(position.realized_pnl) if position.realized_pnl is not None else None,
        opened_at=position.opened_at,
        closed_at=position.closed_at,
    )


@router.get("", response_model=list[PositionResponse])
def list_open_positions(
    symbol: str | None = None, db: Session = Depends(get_db)
) -> list[PositionResponse]:
    return [_to_response(p) for p in get_open_positions(db, symbol)]


@router.post("/{position_id}/monitor", response_model=MonitorResponse)
def monitor_one_position(position_id: str, db: Session = Depends(get_db)) -> MonitorResponse:
    position = get_position(db, position_id)
    if position is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found.")

    try:
        result = monitor_position(db, position)
    except (SeriesNotIngestedError, NoMarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MonitorResponse(
        position=_to_response(result.position),
        current_price=result.current_price,
        thesis_health_score=result.thesis_health.score,
        thesis_health_status=result.thesis_health.status,
        thesis_reasons=result.thesis_health.reasons,
        exit_action=result.decision.action,
        exit_reason=result.decision.reason,
        notes=result.decision.notes,
    )


@router.post("/monitor-all", response_model=list[MonitorResponse])
def monitor_all(db: Session = Depends(get_db)) -> list[MonitorResponse]:
    try:
        results = monitor_all_open_positions(db)
    except (SeriesNotIngestedError, NoMarketDataError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [
        MonitorResponse(
            position=_to_response(r.position),
            current_price=r.current_price,
            thesis_health_score=r.thesis_health.score,
            thesis_health_status=r.thesis_health.status,
            thesis_reasons=r.thesis_health.reasons,
            exit_action=r.decision.action,
            exit_reason=r.decision.reason,
            notes=r.decision.notes,
        )
        for r in results
    ]
