"""
Backtest engine — Stage 9 (docs/RAH_OS_Master_Plan.docx section 13.4).

Walks through historical price bars day by day, and at each day, runs the
EXACT SAME pure calculation functions the live system uses (Market Core's
indicators, Trading Core's trend-pullback detection and classification,
Position Management's target/exit logic) — nothing here is a separate,
parallel implementation that could quietly drift from what actually trades
live. Only the macro side uses a dedicated point-in-time replay
(macro_replay.py), because the live macro service always wants "now," which
doesn't exist in a backtest.

Conservative assumptions, stated plainly:
- No look-ahead: day D's signal uses only bars[0..D] and macro data known
  as of day D's bar date.
- Same-bar stop-vs-target conflicts resolve to the STOP (worst case for the
  trader) — see _resolve_same_bar_conflict.
- One position at a time: a new signal is not evaluated while a simulated
  trade is still open, matching this build's max_open_positions-style
  intent without needing a portfolio-level backtest yet.
- A trade still open when the data runs out is recorded as STILL_OPEN and
  excluded from win/loss statistics — it is not a completed trade.
"""
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from app.market_core.calculations import (
    Bar,
    average_true_range,
    classify_momentum,
    classify_trend,
    rate_of_change,
    simple_moving_average,
)
from app.positions.calculations import compute_target_price
from app.research.data_types import EconomicPoint, PriceBar
from app.research.macro_replay import compute_macro_snapshot_as_of
from app.risk.service import DEFAULT_ATR_STOP_MULTIPLIER
from app.trading_core.calculations import (
    Direction,
    TradeClassification,
    classify_trade,
    detect_trend_pullback,
)

SMA_FAST_PERIOD = 20
SMA_SLOW_PERIOD = 50
ROC_PERIOD = 10
ATR_PERIOD = 14
MIN_BARS_REQUIRED = SMA_SLOW_PERIOD + 5


class TradeExitReason(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    STILL_OPEN = "STILL_OPEN"  # data ran out before either level was hit


@dataclass
class BacktestTrade:
    direction: Direction
    classification: TradeClassification
    entry_date: date
    entry_price: float
    stop_price: float
    target_price: float
    exit_date: date
    exit_price: float
    exit_reason: TradeExitReason
    bars_held: int
    r_multiple: float  # P&L expressed in multiples of the initial risk (1R)


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    bars_evaluated: int = 0
    days_skipped_no_macro_data: int = 0


def _to_calc_bar(bar: PriceBar) -> Bar:
    return Bar(open=bar.open, high=bar.high, low=bar.low, close=bar.close)


def _resolve_same_bar_conflict(
    direction: Direction, bar: PriceBar, stop_price: float, target_price: float
) -> TradeExitReason | None:
    """
    If a single bar's range crosses BOTH the stop and the target (only
    possible with daily bars on a high-volatility day), the conservative
    convention is to assume the stop was hit first — an optimistic backtest
    that always assumes the best-case order would overstate performance.
    """
    if direction is Direction.LONG:
        stop_hit = bar.low <= stop_price
        target_hit = bar.high >= target_price
    else:
        stop_hit = bar.high >= stop_price
        target_hit = bar.low <= target_price

    if stop_hit:
        return TradeExitReason.STOP_LOSS
    if target_hit:
        return TradeExitReason.TAKE_PROFIT
    return None


def _simulate_trade_forward(
    direction: Direction,
    entry_index: int,
    stop_price: float,
    target_price: float,
    bars: list[PriceBar],
) -> tuple[int, float, TradeExitReason]:
    """Walks forward from the bar AFTER entry until the stop or target is hit."""
    for i in range(entry_index + 1, len(bars)):
        bar = bars[i]
        reason = _resolve_same_bar_conflict(direction, bar, stop_price, target_price)
        if reason is TradeExitReason.STOP_LOSS:
            return i, stop_price, reason
        if reason is TradeExitReason.TAKE_PROFIT:
            return i, target_price, reason

    # Ran out of data — close at the last known price, marked STILL_OPEN.
    last_index = len(bars) - 1
    return last_index, bars[last_index].close, TradeExitReason.STILL_OPEN


def run_backtest(
    bars: list[PriceBar],
    economic_series: dict[str, list[EconomicPoint]],
    atr_multiplier: float = DEFAULT_ATR_STOP_MULTIPLIER,
) -> BacktestResult:
    result = BacktestResult()
    if len(bars) < MIN_BARS_REQUIRED:
        return result

    i = MIN_BARS_REQUIRED - 1
    while i < len(bars):
        window = bars[: i + 1]
        closes = [b.close for b in window]
        calc_bars = [_to_calc_bar(b) for b in window]

        sma_fast = simple_moving_average(closes, SMA_FAST_PERIOD)
        sma_slow = simple_moving_average(closes, SMA_SLOW_PERIOD)
        roc_pct = rate_of_change(closes, ROC_PERIOD)
        atr = average_true_range(calc_bars, ATR_PERIOD)

        if sma_fast is None or sma_slow is None or roc_pct is None or atr is None:
            i += 1
            continue

        result.bars_evaluated += 1

        macro_snapshot = compute_macro_snapshot_as_of(economic_series, bars[i].bar_date)
        if macro_snapshot is None:
            result.days_skipped_no_macro_data += 1
            i += 1
            continue

        trend = classify_trend(sma_fast, sma_slow)
        momentum = classify_momentum(roc_pct)
        setup = detect_trend_pullback(trend, momentum, closes[-1], sma_fast)

        if setup.direction is Direction.NONE:
            i += 1
            continue

        classification = classify_trade(setup.direction, macro_snapshot.gold_macro_score)

        entry_price = closes[-1]
        atr_distance = atr * atr_multiplier
        stop_price = (
            entry_price - atr_distance
            if setup.direction is Direction.LONG
            else entry_price + atr_distance
        )
        target_price = compute_target_price(entry_price, stop_price, setup.direction)

        exit_index, exit_price, exit_reason = _simulate_trade_forward(
            setup.direction, i, stop_price, target_price, bars
        )

        one_r = abs(entry_price - stop_price)
        signed_pnl = (
            (exit_price - entry_price)
            if setup.direction is Direction.LONG
            else (entry_price - exit_price)
        )
        r_multiple = (signed_pnl / one_r) if one_r > 0 else 0.0

        result.trades.append(
            BacktestTrade(
                direction=setup.direction,
                classification=classification,
                entry_date=bars[i].bar_date,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                exit_date=bars[exit_index].bar_date,
                exit_price=exit_price,
                exit_reason=exit_reason,
                bars_held=exit_index - i,
                r_multiple=round(r_multiple, 4),
            )
        )

        # No overlapping trades — resume scanning for new setups the day
        # after this one closed (or ended, if it never got to close).
        i = exit_index + 1

    return result
