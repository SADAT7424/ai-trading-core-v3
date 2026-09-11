"""
Unit tests for Risk Governance's pure calculations. Expected values are
hand-computed — see the verification step before these were written.
"""
from app.models.risk import KillSwitchStateName
from app.risk.calculations import (
    RejectionReason,
    RiskConfigInput,
    calculate_position_size,
    evaluate_trade,
)
from app.trading_core.calculations import QualityGrade

_DEFAULT_CONFIG = RiskConfigInput(
    account_balance=10000.0,
    max_risk_per_trade_pct=1.0,
    max_portfolio_heat_pct=5.0,
    max_open_positions=5,
    # High enough that the baseline scenarios below (gold at 3600, a 50pt
    # stop, 1% risk on a $10k account -> ~72% exposure) aren't ALSO clipped
    # by the exposure cap, which would conflate two different mechanisms in
    # the same assertion. The dedicated exposure-cap test below uses its own
    # deliberately tight config instead.
    max_single_asset_exposure_pct=80.0,
    max_daily_loss_pct=3.0,
    min_quality_grade=QualityGrade.C,
)


def test_calculate_position_size() -> None:
    pos = calculate_position_size(10000, 1.0, entry_price=3600, stop_price=3550)
    assert pos.risk_amount == 100.0
    assert pos.units == 2.0
    assert pos.exposure_pct == 72.0


def test_calculate_position_size_zero_stop_distance_is_safe() -> None:
    pos = calculate_position_size(10000, 1.0, entry_price=3600, stop_price=3600)
    assert pos.units == 0.0
    assert pos.risk_amount == 0.0


def test_evaluate_trade_approves_clean_setup() -> None:
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.B,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
    )
    assert decision.approved is True
    assert decision.reasons == []
    assert decision.position is not None
    assert decision.position.risk_amount == 100.0


def test_evaluate_trade_blocks_on_emergency_stop() -> None:
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.EMERGENCY_STOP,
        quality=QualityGrade.A,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
    )
    assert decision.approved is False
    assert RejectionReason.KILL_SWITCH_ACTIVE in decision.reasons
    assert decision.position is None


def test_evaluate_trade_blocks_on_safe_mode() -> None:
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.SAFE_MODE,
        quality=QualityGrade.A,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
    )
    assert decision.approved is False
    assert RejectionReason.KILL_SWITCH_ACTIVE in decision.reasons


def test_evaluate_trade_allows_but_notes_alert_state() -> None:
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.ALERT,
        quality=QualityGrade.B,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
    )
    assert decision.approved is True
    assert any("ALERT" in note for note in decision.notes)


def test_evaluate_trade_rejects_quality_below_minimum() -> None:
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.D,  # config requires at least C
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
    )
    assert decision.approved is False
    assert RejectionReason.QUALITY_BELOW_MINIMUM in decision.reasons


def test_evaluate_trade_rejects_when_max_open_positions_reached() -> None:
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.A,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=5,  # config max_open_positions is 5 — this would be the 6th
        open_portfolio_heat_pct=0.0,
    )
    assert decision.approved is False
    assert RejectionReason.MAX_OPEN_POSITIONS_REACHED in decision.reasons


def test_evaluate_trade_reduces_risk_automatically_rather_than_rejecting() -> None:
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,  # max_risk_per_trade_pct = 1.0
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.A,
        proposed_risk_pct=3.0,  # asking for 3x the allowed risk
        entry_price=3600,
        stop_price=3550,
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
    )
    assert decision.approved is True
    assert decision.position is not None
    assert decision.position.risk_pct == 1.0  # capped, not rejected
    assert any("reduced automatically" in note for note in decision.notes)


def test_evaluate_trade_reduces_size_to_respect_exposure_cap() -> None:
    tight_config = RiskConfigInput(
        account_balance=10000.0,
        max_risk_per_trade_pct=5.0,  # deliberately generous risk allowance...
        max_portfolio_heat_pct=20.0,
        max_open_positions=5,
        max_single_asset_exposure_pct=10.0,  # ...but a tight exposure cap
        max_daily_loss_pct=3.0,
        min_quality_grade=QualityGrade.C,
    )
    decision = evaluate_trade(
        config=tight_config,
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.A,
        proposed_risk_pct=5.0,
        entry_price=3600,
        stop_price=3550,  # tight 50pt stop -> risk alone would want a big position
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
    )
    assert decision.approved is True
    assert decision.position is not None
    assert decision.position.exposure_pct <= 10.0 + 1e-6
    assert decision.position.risk_pct < 5.0  # had to come down from the request


def test_evaluate_trade_rejects_when_portfolio_heat_would_be_exceeded() -> None:
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,  # max_portfolio_heat_pct = 5.0
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.A,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=1,
        open_portfolio_heat_pct=4.5,  # + 1.0 new risk = 5.5, over the 5.0 cap
    )
    assert decision.approved is False
    assert RejectionReason.MAX_PORTFOLIO_HEAT_EXCEEDED in decision.reasons


def test_evaluate_trade_rejects_invalid_stop_distance() -> None:
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.A,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3600,  # no distance at all
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
    )
    assert decision.approved is False
    assert RejectionReason.INVALID_STOP_DISTANCE in decision.reasons


def test_evaluate_trade_blocks_when_daily_loss_limit_reached() -> None:
    """max_daily_loss_pct = 3.0; a $350 loss on $10k is 3.5% — over the limit."""
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.A,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
        today_realized_pnl=-350.0,
    )
    assert decision.approved is False
    assert RejectionReason.MAX_DAILY_LOSS_REACHED in decision.reasons


def test_evaluate_trade_allows_when_daily_loss_under_limit() -> None:
    """A $100 loss on $10k is 1% — comfortably under the 3% limit."""
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.B,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
        today_realized_pnl=-100.0,
    )
    assert decision.approved is True


def test_evaluate_trade_daily_gain_never_blocks() -> None:
    """A positive today_realized_pnl must never trigger the loss check."""
    decision = evaluate_trade(
        config=_DEFAULT_CONFIG,
        kill_switch_state=KillSwitchStateName.NORMAL,
        quality=QualityGrade.B,
        proposed_risk_pct=1.0,
        entry_price=3600,
        stop_price=3550,
        open_positions_count=0,
        open_portfolio_heat_pct=0.0,
        today_realized_pnl=500.0,
    )
    assert decision.approved is True
