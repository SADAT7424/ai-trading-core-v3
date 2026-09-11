"""
Database access for Risk Governance. Kept separate from calculations.py so
the risk rules stay pure and DB-free (see that module's docstring).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.risk import KillSwitchEvent, KillSwitchStateName, RiskConfig


def get_or_create_risk_config(db: Session) -> RiskConfig:
    config = db.execute(
        select(RiskConfig).order_by(RiskConfig.created_at.desc())
    ).scalars().first()
    if config is not None:
        return config

    config = RiskConfig()  # all defaults from the model
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_risk_config(db: Session, **kwargs: object) -> RiskConfig:
    """
    Risk settings are NOT append-only like trade/kill-switch history (there's
    nothing forensically interesting about "what the risk config was" the
    way there is for "what a trade knew at entry") — this genuinely updates
    the single current row. Per AGENTS.md section 8, changing risk limits
    requires the person's explicit action; this function is only ever
    called from an endpoint the person deliberately calls.
    """
    config = get_or_create_risk_config(db)
    for key, value in kwargs.items():
        if value is not None:
            setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config


def get_current_kill_switch_state(db: Session) -> KillSwitchStateName:
    event = db.execute(
        select(KillSwitchEvent).order_by(KillSwitchEvent.created_at.desc())
    ).scalars().first()
    if event is None:
        return KillSwitchStateName.NORMAL
    return KillSwitchStateName(event.state)


def record_kill_switch_event(
    db: Session, state: KillSwitchStateName, reason: str
) -> KillSwitchEvent:
    event = KillSwitchEvent(state=state.value, reason=reason)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
