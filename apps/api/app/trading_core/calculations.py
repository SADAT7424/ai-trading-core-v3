"""
Trading Core — pure calculations (Stage 5 in the master plan,
docs/RAH_OS_Master_Plan.docx section 7). Same discipline as
app/go_os/macro/calculations.py and app/market_core/calculations.py: pure
functions, no database, no AI, fully deterministic and testable.

This is the first, narrowest real slice of the "Opportunity Engine": one
strategy family (Trend Pullback — the first of three listed in section
7.1), combined with the real macro bias from Stage 3 to classify the setup
as macro-aligned, counter-macro, or macro-neutral (section 7.3), and a
transparent, auditable quality score (section 7.4).

Breakout and Liquidity Sweep (the other two initial strategies) are
deliberately not implemented yet — one working, well-tested strategy beats
three shallow ones, consistent with the build philosophy in
docs/DEVELOPMENT_RULES.md.

IMPORTANT — thresholds below are initial, reasonable starting points, not
empirically calibrated. Same caveat as every other engine so far: treat as
defaults to replace once Stage 9 (Research) can backtest them.
"""
from dataclasses import dataclass
from enum import StrEnum

from app.market_core.calculations import Momentum, Trend, VolatilityLevel


class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"  # no setup currently detected


class TradeClassification(StrEnum):
    MACRO_ALIGNED_LONG = "MACRO_ALIGNED_LONG"
    MACRO_ALIGNED_SHORT = "MACRO_ALIGNED_SHORT"
    COUNTER_MACRO_LONG = "COUNTER_MACRO_LONG"
    COUNTER_MACRO_SHORT = "COUNTER_MACRO_SHORT"
    MACRO_NEUTRAL = "MACRO_NEUTRAL"


class QualityGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


# --- Thresholds (initial defaults — see module docstring) -----------------

_PULLBACK_BAND_PCT = 1.5  # how close to the fast SMA counts as "pulled back to it"
_MACRO_ALIGNED_THRESHOLD = 15  # gold_score magnitude above which macro counts as a real tailwind
_MACRO_COUNTER_THRESHOLD = -15


@dataclass
class PullbackSetup:
    direction: Direction
    distance_to_fast_sma_pct: float  # signed: positive = above, negative = below
    technical_score: float  # 0-100, meaningless when direction is NONE


def detect_trend_pullback(
    trend: Trend,
    momentum: Momentum,
    latest_close: float,
    sma_fast: float,
    band_pct: float = _PULLBACK_BAND_PCT,
) -> PullbackSetup:
    """
    Trend Pullback: an established trend (per Market Core) where price has
    retraced close to the fast moving average without momentum having
    flipped against the trend — the classic "buy the dip in an uptrend" (or
    mirror for downtrends) setup.

    Deliberately excludes momentum actively opposing the trend direction:
    that's a different situation (a potential trend change), not a pullback.
    """
    if sma_fast == 0:
        return PullbackSetup(Direction.NONE, 0.0, 0.0)

    distance_pct = ((latest_close - sma_fast) / abs(sma_fast)) * 100
    within_band = abs(distance_pct) <= band_pct

    if trend is Trend.BULLISH and momentum is not Momentum.NEGATIVE and within_band:
        direction = Direction.LONG
    elif trend is Trend.BEARISH and momentum is not Momentum.POSITIVE and within_band:
        direction = Direction.SHORT
    else:
        return PullbackSetup(Direction.NONE, round(distance_pct, 3), 0.0)

    # Closer to the fast SMA = a tighter, higher-quality pullback.
    closeness_score = max(0.0, 100 - (abs(distance_pct) / band_pct) * 100)
    momentum_matches = (direction is Direction.LONG and momentum is Momentum.POSITIVE) or (
        direction is Direction.SHORT and momentum is Momentum.NEGATIVE
    )
    momentum_bonus = 15.0 if momentum_matches else 0.0
    technical_score = min(100.0, closeness_score * 0.85 + momentum_bonus)

    return PullbackSetup(direction, round(distance_pct, 3), round(technical_score, 2))


def classify_trade(direction: Direction, gold_macro_score: int) -> TradeClassification:
    """
    Per section 7.3: is this setup aligned with, opposed to, or independent
    of the current macro bias for the asset?
    """
    if direction is Direction.LONG:
        if gold_macro_score >= _MACRO_ALIGNED_THRESHOLD:
            return TradeClassification.MACRO_ALIGNED_LONG
        if gold_macro_score <= _MACRO_COUNTER_THRESHOLD:
            return TradeClassification.COUNTER_MACRO_LONG
        return TradeClassification.MACRO_NEUTRAL

    if direction is Direction.SHORT:
        if gold_macro_score <= _MACRO_COUNTER_THRESHOLD:
            return TradeClassification.MACRO_ALIGNED_SHORT
        if gold_macro_score >= _MACRO_ALIGNED_THRESHOLD:
            return TradeClassification.COUNTER_MACRO_SHORT
        return TradeClassification.MACRO_NEUTRAL

    return TradeClassification.MACRO_NEUTRAL


@dataclass
class OpportunityScore:
    technical_score: float
    macro_alignment_score: float  # 0-100, direction-adjusted
    overall_score: float
    quality: QualityGrade


def _macro_alignment_score_0_100(direction: Direction, gold_macro_score: int) -> float:
    """
    Maps the macro gold score (roughly -110..+110, see go_os/macro) onto a
    0-100 scale FROM THIS SETUP'S PERSPECTIVE: a bullish macro score helps a
    LONG setup and hurts a SHORT setup, and vice versa.
    """
    directional_score = gold_macro_score if direction is Direction.LONG else -gold_macro_score
    clamped = max(-100, min(100, directional_score))
    return (clamped + 100) / 2


def compute_opportunity_score(
    direction: Direction,
    technical_score: float,
    gold_macro_score: int,
    volatility: VolatilityLevel,
) -> OpportunityScore:
    macro_alignment_score = _macro_alignment_score_0_100(direction, gold_macro_score)
    overall_score = round(0.6 * technical_score + 0.4 * macro_alignment_score, 2)

    # High volatility caps quality regardless of how good the setup looks —
    # position sizing/management needs to be more conservative either way
    # (see master plan section 9.5), so the grade should reflect that.
    if volatility is VolatilityLevel.HIGH:
        if overall_score >= 65:
            quality = QualityGrade.C
        else:
            quality = QualityGrade.D
    elif overall_score >= 80:
        quality = QualityGrade.A
    elif overall_score >= 65:
        quality = QualityGrade.B
    elif overall_score >= 50:
        quality = QualityGrade.C
    else:
        quality = QualityGrade.D

    return OpportunityScore(
        technical_score=technical_score,
        macro_alignment_score=round(macro_alignment_score, 2),
        overall_score=overall_score,
        quality=quality,
    )
