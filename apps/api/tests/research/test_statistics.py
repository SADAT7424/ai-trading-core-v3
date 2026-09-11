"""
Tests for backtest statistics — expected values hand-computed, see the
verification step before this was written.
"""
from datetime import date

from app.research.backtest import BacktestTrade, TradeExitReason
from app.research.statistics import compute_backtest_statistics
from app.trading_core.calculations import Direction, TradeClassification


def _trade(
    r_multiple: float, exit_reason: TradeExitReason = TradeExitReason.TAKE_PROFIT
) -> BacktestTrade:
    return BacktestTrade(
        direction=Direction.LONG,
        classification=TradeClassification.MACRO_ALIGNED_LONG,
        entry_date=date(2024, 1, 1),
        entry_price=100.0,
        stop_price=90.0,
        target_price=120.0,
        exit_date=date(2024, 1, 2),
        exit_price=100.0 + r_multiple * 10,
        exit_reason=exit_reason,
        bars_held=1,
        r_multiple=r_multiple,
    )


def test_empty_trades_returns_zeros() -> None:
    stats = compute_backtest_statistics([])
    assert stats.total_trades == 0
    assert stats.profit_factor is None
    assert stats.equity_curve_r == []


def test_still_open_trades_excluded_from_stats() -> None:
    trades = [_trade(2.0), _trade(0.0, TradeExitReason.STILL_OPEN)]
    stats = compute_backtest_statistics(trades)
    assert stats.total_trades == 1
    assert stats.still_open_trades == 1


def test_equity_curve_and_drawdown() -> None:
    r_sequence = [2, 1, -1, -1, -1, 3]
    trades = [_trade(r) for r in r_sequence]
    stats = compute_backtest_statistics(trades)

    assert stats.equity_curve_r == [2.0, 3.0, 2.0, 1.0, 0.0, 3.0]
    assert stats.max_drawdown_r == 3.0  # peak 3 -> trough 0
    assert stats.total_r == 3.0
    assert stats.win_rate_pct == 50.0
    assert stats.profit_factor == 2.0  # gross profit 6 / gross loss 3


def test_all_wins_has_no_profit_factor_denominator() -> None:
    trades = [_trade(1.0), _trade(2.0)]
    stats = compute_backtest_statistics(trades)
    assert stats.losses == 0
    assert stats.profit_factor is None
