"""
Unit tests for Position Management's pure calculations. Expected values are
hand-computed — see the verification step before these were written.
"""
from app.market_core.calculations import Trend
from app.positions.calculations import (
    ExitAction,
    ExitReason,
    ThesisHealthStatus,
    compute_target_price,
    compute_thesis_health,
    compute_trailing_stop,
    decide_exit,
)
from app.trading_core.calculations import Direction


def test_compute_target_price_long() -> None:
    assert compute_target_price(3600, 3550, Direction.LONG, r_multiple=2.0) == 3700.0


def test_compute_target_price_short() -> None:
    assert compute_target_price(3600, 3650, Direction.SHORT, r_multiple=2.0) == 3500.0


def test_thesis_health_fully_intact_scores_strong() -> None:
    health = compute_thesis_health(
        Direction.LONG,
        current_trend=Trend.BULLISH,
        entry_gold_macro_score=40,
        current_gold_macro_score=40,
    )
    assert health.score == 100
    assert health.status is ThesisHealthStatus.STRONG


def test_thesis_health_trend_flip_is_severe() -> None:
    health = compute_thesis_health(
        Direction.LONG,
        current_trend=Trend.BEARISH,
        entry_gold_macro_score=40,
        current_gold_macro_score=40,
    )
    assert health.score == 50  # 100 - 50 (trend opposed)
    assert health.status is ThesisHealthStatus.CRITICAL


def test_thesis_health_both_opposed_is_invalidated() -> None:
    health = compute_thesis_health(
        Direction.LONG,
        current_trend=Trend.BEARISH,
        entry_gold_macro_score=40,
        current_gold_macro_score=-40,
    )
    assert health.score == 15  # 100 - 50 - 35
    assert health.status is ThesisHealthStatus.INVALIDATED


def test_thesis_health_neutral_drift_is_weakening_not_invalidated() -> None:
    health = compute_thesis_health(
        Direction.LONG,
        current_trend=Trend.NEUTRAL,
        entry_gold_macro_score=40,
        current_gold_macro_score=5,  # no longer a strong tailwind, but not opposed
    )
    assert health.score == 65  # 100 - 20 (trend neutral) - 15 (macro no longer aligned)
    assert health.status is ThesisHealthStatus.WEAKENING


def test_decide_exit_hard_stop_wins_even_with_strong_thesis() -> None:
    """The single most important rule in this module — see docstring."""
    decision = decide_exit(
        Direction.LONG,
        current_price=3549,
        stop_price=3550,
        target_price=3700,
        thesis_status=ThesisHealthStatus.STRONG,
    )
    assert decision.action is ExitAction.EXIT
    assert decision.reason is ExitReason.STOP_LOSS


def test_decide_exit_target_reached() -> None:
    decision = decide_exit(
        Direction.LONG,
        current_price=3701,
        stop_price=3550,
        target_price=3700,
        thesis_status=ThesisHealthStatus.HEALTHY,
    )
    assert decision.action is ExitAction.EXIT
    assert decision.reason is ExitReason.TAKE_PROFIT


def test_decide_exit_invalidated_thesis_exits_even_mid_range() -> None:
    decision = decide_exit(
        Direction.LONG,
        current_price=3620,  # nowhere near stop or target
        stop_price=3550,
        target_price=3700,
        thesis_status=ThesisHealthStatus.INVALIDATED,
    )
    assert decision.action is ExitAction.EXIT
    assert decision.reason is ExitReason.THESIS_INVALIDATED


def test_decide_exit_holds_when_nothing_triggers() -> None:
    decision = decide_exit(
        Direction.LONG,
        current_price=3620,
        stop_price=3550,
        target_price=3700,
        thesis_status=ThesisHealthStatus.HEALTHY,
    )
    assert decision.action is ExitAction.HOLD
    assert decision.reason is ExitReason.NONE


def test_decide_exit_short_direction_mirrors_long() -> None:
    decision = decide_exit(
        Direction.SHORT,
        current_price=3651,  # above stop for a short -> stop breached
        stop_price=3650,
        target_price=3500,
        thesis_status=ThesisHealthStatus.STRONG,
    )
    assert decision.action is ExitAction.EXIT
    assert decision.reason is ExitReason.STOP_LOSS


def test_trailing_stop_no_move_before_breakeven_trigger() -> None:
    # Entry 3600, stop 3550 (1R = 50). At +0.5R, nothing should move yet.
    new_stop = compute_trailing_stop(
        Direction.LONG,
        entry_price=3600,
        initial_stop_price=3550,
        current_stop_price=3550,
        current_price=3625,
        atr=10,
    )
    assert new_stop == 3550


def test_trailing_stop_moves_to_breakeven_at_1r() -> None:
    new_stop = compute_trailing_stop(
        Direction.LONG,
        entry_price=3600,
        initial_stop_price=3550,
        current_stop_price=3550,
        current_price=3650,  # exactly +1R
        atr=10,
    )
    assert new_stop == 3600  # breakeven


def test_trailing_stop_trails_beyond_1r() -> None:
    # +2R (3700), ATR=10, multiplier=1.5 -> candidate = 3700 - 15 = 3685
    new_stop = compute_trailing_stop(
        Direction.LONG,
        entry_price=3600,
        initial_stop_price=3550,
        current_stop_price=3600,  # already at breakeven from a prior check
        current_price=3700,
        atr=10,
    )
    assert new_stop == 3685


def test_trailing_stop_never_moves_backward() -> None:
    # Stop already trailed to 3685; a pullback to +1.4R should NOT loosen it.
    new_stop = compute_trailing_stop(
        Direction.LONG,
        entry_price=3600,
        initial_stop_price=3550,
        current_stop_price=3685,
        current_price=3670,  # a pullback from the highs
        atr=10,
    )
    assert new_stop == 3685  # unchanged, not loosened to 3670-15=3655


def test_trailing_stop_short_direction_mirrors_long() -> None:
    # Entry 3600, initial stop 3650 (1R=50) SHORT. At +2R (price 3500), ATR=10.
    new_stop = compute_trailing_stop(
        Direction.SHORT,
        entry_price=3600,
        initial_stop_price=3650,
        current_stop_price=3600,
        current_price=3500,
        atr=10,
    )
    assert new_stop == 3515  # 3500 + 15
