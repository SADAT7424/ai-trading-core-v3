"""
Position Management — pure calculations (Stage 8 in the master plan,
docs/RAH_OS_Master_Plan.docx section 11). Same discipline as every other
engine so far: pure functions, no database, no AI, fully deterministic.

Two rules from the master plan drive this module's structure:
- "Hard Stop Always Wins" (section 11.3): risk controls take absolute
  precedence — decide_exit() checks the stop before anything else, and
  nothing below it can override that.
- Thesis health is judged on whether the ORIGINAL reason for the trade
  still holds (trend + macro alignment), not on unrealized P&L alone — a
  losing position can have a perfectly healthy thesis, and a profitable one
  can have an invalidated thesis that should be exited anyway.

IMPORTANT — thresholds below are initial, reasonable starting points, not
empirically calibrated. Same caveat as every other engine in this project.
"""
from dataclasses import dataclass
from enum import StrEnum

from app.market_core.calculations import Trend
from app.trading_core.calculations import Direction

_DEFAULT_TARGET_R_MULTIPLE = 2.0  # target distance = 2x the stop distance ("2R")

_MACRO_STRONG_THRESHOLD = 15  # matches trading_core's alignment threshold


class ThesisHealthStatus(StrEnum):
    STRONG = "STRONG"
    HEALTHY = "HEALTHY"
    WEAKENING = "WEAKENING"
    CRITICAL = "CRITICAL"
    INVALIDATED = "INVALIDATED"


class ExitAction(StrEnum):
    HOLD = "HOLD"
    EXIT = "EXIT"


class ExitReason(StrEnum):
    NONE = "NONE"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    THESIS_INVALIDATED = "THESIS_INVALIDATED"


def compute_target_price(
    entry_price: float,
    stop_price: float,
    direction: Direction,
    r_multiple: float = _DEFAULT_TARGET_R_MULTIPLE,
) -> float:
    stop_distance = abs(entry_price - stop_price)
    target_distance = stop_distance * r_multiple
    if direction is Direction.LONG:
        return round(entry_price + target_distance, 6)
    return round(entry_price - target_distance, 6)


_BREAKEVEN_TRIGGER_R = 1.0  # move stop to breakeven once price has moved 1R favorably
_ATR_TRAIL_MULTIPLIER = 1.5  # beyond breakeven, trail this many ATRs behind price


def compute_trailing_stop(
    direction: Direction,
    entry_price: float,
    initial_stop_price: float,
    current_stop_price: float,
    current_price: float,
    atr: float,
) -> float:
    """
    Two-stage trailing, matching the master plan's "dynamic risk reduction"
    (section 11.4): once a trade has moved 1R in its favor, the stop moves
    to breakeven (locking in "can no longer lose money" on this trade).
    Beyond that, the stop trails behind price by a multiple of ATR.

    The stop only ever moves to REDUCE risk (tighten toward/past price) —
    it can never move backward, even if this function is called with a
    less favorable current_price than a previous call (e.g. a pullback
    that hasn't broken the trend). That monotonicity is the whole point of
    a trailing stop; violating it would defeat the purpose.
    """
    one_r = abs(entry_price - initial_stop_price)
    if one_r == 0:
        return current_stop_price

    if direction is Direction.LONG:
        profit_in_r = (current_price - entry_price) / one_r
        candidates = [current_stop_price]
        if profit_in_r >= _BREAKEVEN_TRIGGER_R:
            candidates.append(entry_price)
        if profit_in_r > _BREAKEVEN_TRIGGER_R:
            candidates.append(current_price - atr * _ATR_TRAIL_MULTIPLIER)
        return round(max(candidates), 6)

    # SHORT: mirror image — profit is price falling, stop only ever moves down.
    profit_in_r = (entry_price - current_price) / one_r
    candidates = [current_stop_price]
    if profit_in_r >= _BREAKEVEN_TRIGGER_R:
        candidates.append(entry_price)
    if profit_in_r > _BREAKEVEN_TRIGGER_R:
        candidates.append(current_price + atr * _ATR_TRAIL_MULTIPLIER)
    return round(min(candidates), 6)


@dataclass
class ThesisHealth:
    score: int
    status: ThesisHealthStatus
    reasons: list[str]


def compute_thesis_health(
    direction: Direction,
    current_trend: Trend,
    entry_gold_macro_score: int,
    current_gold_macro_score: int,
) -> ThesisHealth:
    """
    Starts at 100 and subtracts points for the two things that actually
    justified the trade at entry (per Stage 5's classification) no longer
    holding: market trend alignment and macro alignment. This deliberately
    does NOT look at unrealized P&L — see module docstring.
    """
    score = 100
    reasons: list[str] = []

    trend_aligned = (direction is Direction.LONG and current_trend is Trend.BULLISH) or (
        direction is Direction.SHORT and current_trend is Trend.BEARISH
    )
    trend_opposed = (direction is Direction.LONG and current_trend is Trend.BEARISH) or (
        direction is Direction.SHORT and current_trend is Trend.BULLISH
    )

    if trend_opposed:
        score -= 50
        reasons.append(f"Market trend has flipped to {current_trend.value}, against the position.")
    elif not trend_aligned:
        score -= 20
        reasons.append("Market trend has gone neutral — the original trend is no longer clear.")

    macro_aligned_now = (
        direction is Direction.LONG and current_gold_macro_score >= _MACRO_STRONG_THRESHOLD
    ) or (direction is Direction.SHORT and current_gold_macro_score <= -_MACRO_STRONG_THRESHOLD)
    macro_opposed_now = (
        direction is Direction.LONG and current_gold_macro_score <= -_MACRO_STRONG_THRESHOLD
    ) or (direction is Direction.SHORT and current_gold_macro_score >= _MACRO_STRONG_THRESHOLD)

    if macro_opposed_now:
        score -= 35
        reasons.append(
            f"Macro backdrop has turned against the position "
            f"(score now {current_gold_macro_score})."
        )
    elif not macro_aligned_now:
        score -= 15
        reasons.append("Macro backdrop is no longer a clear tailwind.")

    score = max(0, min(100, score))

    if score >= 90:
        status = ThesisHealthStatus.STRONG
    elif score >= 75:
        status = ThesisHealthStatus.HEALTHY
    elif score >= 60:
        status = ThesisHealthStatus.WEAKENING
    elif score >= 40:
        status = ThesisHealthStatus.CRITICAL
    else:
        status = ThesisHealthStatus.INVALIDATED

    if not reasons:
        reasons.append("Trend and macro both still support the original thesis.")

    return ThesisHealth(score=score, status=status, reasons=reasons)


@dataclass
class ExitDecision:
    action: ExitAction
    reason: ExitReason
    notes: list[str]


def decide_exit(
    direction: Direction,
    current_price: float,
    stop_price: float,
    target_price: float,
    thesis_status: ThesisHealthStatus,
) -> ExitDecision:
    """
    Checked in priority order per the master plan's risk hierarchy: the
    hard stop is checked FIRST and unconditionally — nothing below this
    point can keep a position open once the stop is breached, no matter how
    healthy the thesis looks.
    """
    stop_breached = (direction is Direction.LONG and current_price <= stop_price) or (
        direction is Direction.SHORT and current_price >= stop_price
    )
    if stop_breached:
        return ExitDecision(
            action=ExitAction.EXIT,
            reason=ExitReason.STOP_LOSS,
            notes=["Hard stop breached — exits regardless of thesis health."],
        )

    target_reached = (direction is Direction.LONG and current_price >= target_price) or (
        direction is Direction.SHORT and current_price <= target_price
    )
    if target_reached:
        return ExitDecision(
            action=ExitAction.EXIT, reason=ExitReason.TAKE_PROFIT, notes=["Target reached."]
        )

    if thesis_status is ThesisHealthStatus.INVALIDATED:
        return ExitDecision(
            action=ExitAction.EXIT,
            reason=ExitReason.THESIS_INVALIDATED,
            notes=[
                "Thesis health has fallen to INVALIDATED — exiting even "
                "though price hasn't hit stop/target."
            ],
        )

    return ExitDecision(
        action=ExitAction.HOLD,
        reason=ExitReason.NONE,
        notes=["No exit condition met — holding is a valid, deliberate decision, not inaction."],
    )
