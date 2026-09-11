"""
Backtest aggregate statistics — pure calculations over a list of completed
trades. Same discipline as app/performance/calculations.py, expressed in R
(risk multiples) instead of dollars, since a backtest doesn't know what
account size or risk % a person will actually use — R keeps results
comparable regardless of position sizing (see master plan section 12.8).
"""
from dataclasses import dataclass

from app.research.backtest import BacktestTrade, TradeExitReason


@dataclass
class BacktestStatistics:
    total_trades: int  # completed only — STILL_OPEN trades are excluded
    still_open_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    total_r: float
    average_r: float
    profit_factor: float | None
    max_drawdown_r: float
    equity_curve_r: list[float]  # cumulative R after each completed trade, in order


def compute_backtest_statistics(trades: list[BacktestTrade]) -> BacktestStatistics:
    completed = [t for t in trades if t.exit_reason is not TradeExitReason.STILL_OPEN]
    still_open = len(trades) - len(completed)

    if not completed:
        return BacktestStatistics(
            total_trades=0,
            still_open_trades=still_open,
            wins=0,
            losses=0,
            win_rate_pct=0.0,
            total_r=0.0,
            average_r=0.0,
            profit_factor=None,
            max_drawdown_r=0.0,
            equity_curve_r=[],
        )

    r_values = [t.r_multiple for t in completed]
    wins_list = [r for r in r_values if r > 0]
    losses_list = [r for r in r_values if r < 0]

    total_r = sum(r_values)
    equity_curve: list[float] = []
    running = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for r in r_values:
        running += r
        equity_curve.append(round(running, 4))
        peak = max(peak, running)
        max_drawdown = max(max_drawdown, peak - running)

    gross_profit = sum(wins_list)
    gross_loss = abs(sum(losses_list))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    return BacktestStatistics(
        total_trades=len(completed),
        still_open_trades=still_open,
        wins=len(wins_list),
        losses=len(losses_list),
        win_rate_pct=round((len(wins_list) / len(completed)) * 100, 2),
        total_r=round(total_r, 4),
        average_r=round(total_r / len(completed), 4),
        profit_factor=round(profit_factor, 3) if profit_factor is not None else None,
        max_drawdown_r=round(max_drawdown, 4),
        equity_curve_r=equity_curve,
    )
