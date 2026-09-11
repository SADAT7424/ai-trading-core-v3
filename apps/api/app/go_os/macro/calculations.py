"""
Macro Regime Engine — pure calculations (Stage 3 / "GO-03" in the master
plan, docs/RAH_OS_Master_Plan.docx section 5.4).

Every function here is a pure function: given the same numbers, it always
returns the same classification. No database access, no AI, no randomness —
per AGENTS.md, this is exactly the kind of thing that must be deterministic
and independently unit-testable.

IMPORTANT — these thresholds are initial, reasonable starting points, not
empirically calibrated values. The master plan explicitly calls this out for
the Economic Surprise Engine (section 5.3) and the same caution applies
here: treat these as defaults to be replaced once Stage 9 (Research) can
backtest and calibrate them against real history.
"""
from dataclasses import dataclass
from enum import StrEnum


class InflationLevel(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class Trend(StrEnum):
    RISING = "RISING"
    FALLING = "FALLING"
    FLAT = "FLAT"


class EmploymentCondition(StrEnum):
    STRENGTHENING = "STRENGTHENING"
    STABLE = "STABLE"
    WEAKENING = "WEAKENING"


class PolicyStance(StrEnum):
    DOVISH = "DOVISH"
    NEUTRAL = "NEUTRAL"
    HAWKISH = "HAWKISH"


class RealYieldLevel(StrEnum):
    NEGATIVE = "NEGATIVE"  # historically bullish for gold
    LOW = "LOW"
    HIGH = "HIGH"  # historically bearish for gold


class MacroRegime(StrEnum):
    REFLATION = "REFLATION"  # strong growth + high/rising inflation
    STAGFLATION = "STAGFLATION"  # weak growth + high/rising inflation
    GOLDILOCKS = "GOLDILOCKS"  # strong growth + low/falling inflation
    DEFLATIONARY = "DEFLATIONARY"  # weak growth + low/falling inflation


class GoldBias(StrEnum):
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"


# --- Thresholds (initial defaults — see module docstring) -----------------

_INFLATION_HIGH_PCT = 4.0
_INFLATION_LOW_PCT = 2.0
_TREND_FLAT_BAND = 0.05  # a change smaller than this (in the same units) counts as "flat"
_REAL_YIELD_HIGH_PCT = 1.0
_REAL_YIELD_LOW_PCT = 0.0


def classify_trend(change: float, flat_band: float = _TREND_FLAT_BAND) -> Trend:
    if change > flat_band:
        return Trend.RISING
    if change < -flat_band:
        return Trend.FALLING
    return Trend.FLAT


def classify_inflation_level(yoy_pct: float) -> InflationLevel:
    if yoy_pct >= _INFLATION_HIGH_PCT:
        return InflationLevel.HIGH
    if yoy_pct <= _INFLATION_LOW_PCT:
        return InflationLevel.LOW
    return InflationLevel.MODERATE


def classify_employment_condition(unemployment_trend: Trend) -> EmploymentCondition:
    if unemployment_trend is Trend.FALLING:
        return EmploymentCondition.STRENGTHENING
    if unemployment_trend is Trend.RISING:
        return EmploymentCondition.WEAKENING
    return EmploymentCondition.STABLE


def classify_policy_stance(fed_funds_trend: Trend) -> PolicyStance:
    if fed_funds_trend is Trend.RISING:
        return PolicyStance.HAWKISH
    if fed_funds_trend is Trend.FALLING:
        return PolicyStance.DOVISH
    return PolicyStance.NEUTRAL


def classify_real_yield(real_yield_pct: float) -> RealYieldLevel:
    if real_yield_pct >= _REAL_YIELD_HIGH_PCT:
        return RealYieldLevel.HIGH
    if real_yield_pct <= _REAL_YIELD_LOW_PCT:
        return RealYieldLevel.NEGATIVE
    return RealYieldLevel.LOW


def classify_macro_regime(
    inflation_level: InflationLevel,
    inflation_trend: Trend,
    employment_condition: EmploymentCondition,
) -> MacroRegime:
    inflation_hot = inflation_level is InflationLevel.HIGH or inflation_trend is Trend.RISING
    growth_strong = employment_condition is not EmploymentCondition.WEAKENING

    if inflation_hot and growth_strong:
        return MacroRegime.REFLATION
    if inflation_hot and not growth_strong:
        return MacroRegime.STAGFLATION
    if not inflation_hot and growth_strong:
        return MacroRegime.GOLDILOCKS
    return MacroRegime.DEFLATIONARY


@dataclass
class GoldScoreBreakdown:
    real_yield_contribution: int
    inflation_contribution: int
    policy_contribution: int

    @property
    def total(self) -> int:
        return (
            self.real_yield_contribution
            + self.inflation_contribution
            + self.policy_contribution
        )

    @property
    def bias(self) -> GoldBias:
        if self.total >= 20:
            return GoldBias.BULLISH
        if self.total <= -20:
            return GoldBias.BEARISH
        return GoldBias.NEUTRAL


def compute_gold_macro_score(
    real_yield_level: RealYieldLevel,
    inflation_level: InflationLevel,
    policy_stance: PolicyStance,
) -> GoldScoreBreakdown:
    """
    A simplified, transparent version of the master plan's Asset Impact
    Engine (section 5.5) for gold specifically. Each factor contributes
    independently on a fixed scale so the reasoning stays auditable — this
    is deliberately not a black box.
    """
    real_yield_contribution = {
        RealYieldLevel.NEGATIVE: 35,
        RealYieldLevel.LOW: 10,
        RealYieldLevel.HIGH: -35,
    }[real_yield_level]

    inflation_contribution = {
        InflationLevel.HIGH: 25,
        InflationLevel.MODERATE: 5,
        InflationLevel.LOW: -10,
    }[inflation_level]

    policy_contribution = {
        PolicyStance.DOVISH: 25,
        PolicyStance.NEUTRAL: 0,
        PolicyStance.HAWKISH: -25,
    }[policy_stance]

    return GoldScoreBreakdown(
        real_yield_contribution=real_yield_contribution,
        inflation_contribution=inflation_contribution,
        policy_contribution=policy_contribution,
    )
