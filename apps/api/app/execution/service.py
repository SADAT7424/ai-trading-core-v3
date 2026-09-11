"""
Execution — service layer. Takes a Stage 6 risk evaluation and, only if
approved, places a (paper) order and persists the result. Rejected
evaluations are persisted too — a rejected order is still a fact worth
recording (see AGENTS.md section 4 on audit trails), not silently discarded.
"""
from sqlalchemy.orm import Session

from app.execution.paper_broker import PaperBrokerAdapter
from app.models.execution import Order, OrderStatus
from app.positions.service import open_position_from_order
from app.risk.service import evaluate_trade_for_symbol
from app.trading_core.calculations import Direction


def submit_paper_order(
    db: Session,
    symbol: str,
    interval: str = "1day",
    proposed_risk_pct: float | None = None,
) -> Order:
    """
    Runs the full pipeline (opportunity -> risk) and, if approved, places a
    paper order. Always persists an Order row — approved and rejected alike
    — so nothing evaluated is ever lost, only ever acted on or not.
    """
    evaluation = evaluate_trade_for_symbol(
        db,
        symbol,
        interval,
        proposed_risk_pct=proposed_risk_pct,
    )

    if evaluation.direction is Direction.NONE or not evaluation.decision.approved:
        order = Order(
            symbol=symbol,
            direction=evaluation.direction.value,
            status=OrderStatus.REJECTED,
            requested_price=evaluation.entry_price,
            stop_price=evaluation.stop_price or evaluation.entry_price,
            units=0.0,
            risk_amount=0.0,
            risk_pct=0.0,
            quality_grade=evaluation.quality.value if evaluation.quality else None,
            classification=evaluation.classification,
            entry_gold_macro_score=evaluation.gold_macro_score,
            rejection_reasons=",".join(r.value for r in evaluation.decision.reasons) or "NO_SETUP",
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    assert evaluation.decision.position is not None  # guaranteed by approved=True

    broker = PaperBrokerAdapter(db=db, interval=interval)
    fill = broker.place_market_order(
        symbol=symbol,
        direction=evaluation.direction.value,
        units=evaluation.decision.position.units,
    )

    order = Order(
        symbol=symbol,
        direction=evaluation.direction.value,
        status=OrderStatus.FILLED,
        broker="PAPER",
        requested_price=evaluation.entry_price,
        filled_price=fill.filled_price,
        stop_price=evaluation.stop_price or evaluation.entry_price,
        units=evaluation.decision.position.units,
        risk_amount=evaluation.decision.position.risk_amount,
        risk_pct=evaluation.decision.position.risk_pct,
        quality_grade=evaluation.quality.value if evaluation.quality else None,
        classification=evaluation.classification,
        entry_gold_macro_score=evaluation.gold_macro_score,
        filled_at=fill.filled_at,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Stage 8: a filled order immediately becomes a tracked, monitorable
    # position — see app/positions/service.py.
    open_position_from_order(db, order)

    return order
