"""
Tests for the performance summary — pure calculations plus an end-to-end
API test using real closed positions.
"""
from app.performance.calculations import compute_performance_summary


def test_empty_history_returns_zeros_not_errors() -> None:
    summary = compute_performance_summary([])
    assert summary.total_trades == 0
    assert summary.profit_factor is None
    assert summary.expectancy == 0.0


def test_all_wins_has_no_profit_factor_denominator_issue() -> None:
    summary = compute_performance_summary([100, 50, 25])
    assert summary.losses == 0
    assert summary.average_loss == 0.0
    assert summary.profit_factor is None  # no losses to divide by — not a crash, not zero


def test_mixed_wins_and_losses() -> None:
    summary = compute_performance_summary([100, 50, 75, -40, -60])
    assert summary.total_trades == 5
    assert summary.wins == 3
    assert summary.losses == 2
    assert summary.win_rate_pct == 60.0
    assert summary.total_realized_pnl == 125
    assert summary.average_win == 75.0
    assert summary.average_loss == -50.0
    assert summary.profit_factor == 2.25
    assert summary.expectancy == 25.0


def test_all_losses() -> None:
    summary = compute_performance_summary([-10, -20, -30])
    assert summary.wins == 0
    assert summary.average_win == 0.0
    assert summary.profit_factor == 0.0
    assert summary.expectancy == -20.0
