"""
Performance summary — pure calculations. Computed fresh from existing
closed-position data (Stage 8) on every request, same no-persistence
approach as the macro/market/opportunity engines. No schema changes: this
reads data that already exists, it doesn't store anything new.
"""
from dataclasses import dataclass


@dataclass
class PerformanceSummary:
    total_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    total_realized_pnl: float
    average_win: float
    average_loss: float  # stored as a negative number, or 0.0 if no losses
    profit_factor: float | None  # None when there are no losses to divide by
    expectancy: float  # average P&L per trade


def compute_performance_summary(realized_pnls: list[float]) -> PerformanceSummary:
    total_trades = len(realized_pnls)
    if total_trades == 0:
        return PerformanceSummary(
            total_trades=0,
            wins=0,
            losses=0,
            win_rate_pct=0.0,
            total_realized_pnl=0.0,
            average_win=0.0,
            average_loss=0.0,
            profit_factor=None,
            expectancy=0.0,
        )

    wins_list = [p for p in realized_pnls if p > 0]
    losses_list = [p for p in realized_pnls if p < 0]

    wins = len(wins_list)
    losses = len(losses_list)
    win_rate_pct = (wins / total_trades) * 100
    total_realized_pnl = sum(realized_pnls)
    average_win = (sum(wins_list) / wins) if wins else 0.0
    average_loss = (sum(losses_list) / losses) if losses else 0.0

    gross_profit = sum(wins_list)
    gross_loss = abs(sum(losses_list))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    expectancy = total_realized_pnl / total_trades

    return PerformanceSummary(
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        win_rate_pct=round(win_rate_pct, 2),
        total_realized_pnl=round(total_realized_pnl, 2),
        average_win=round(average_win, 2),
        average_loss=round(average_loss, 2),
        profit_factor=round(profit_factor, 3) if profit_factor is not None else None,
        expectancy=round(expectancy, 2),
    )
