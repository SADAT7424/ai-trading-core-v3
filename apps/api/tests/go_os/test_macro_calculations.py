"""
Unit tests for the Macro Regime Engine's pure calculations. No database, no
network — these test the classification rules directly.
"""
from app.go_os.macro.calculations import (
    DollarCondition,
    EmploymentCondition,
    GoldBias,
    InflationLevel,
    MacroRegime,
    PolicyStance,
    RealYieldLevel,
    Trend,
    classify_dollar_condition,
    classify_employment_condition,
    classify_inflation_level,
    classify_macro_regime,
    classify_policy_stance,
    classify_real_yield,
    classify_trend,
    compute_gold_macro_score,
)


def test_classify_trend() -> None:
    assert classify_trend(1.0) is Trend.RISING
    assert classify_trend(-1.0) is Trend.FALLING
    assert classify_trend(0.01) is Trend.FLAT


def test_classify_inflation_level() -> None:
    assert classify_inflation_level(5.0) is InflationLevel.HIGH
    assert classify_inflation_level(3.0) is InflationLevel.MODERATE
    assert classify_inflation_level(1.0) is InflationLevel.LOW
    # Boundary values
    assert classify_inflation_level(4.0) is InflationLevel.HIGH
    assert classify_inflation_level(2.0) is InflationLevel.LOW


def test_classify_employment_condition() -> None:
    assert classify_employment_condition(Trend.FALLING) is EmploymentCondition.STRENGTHENING
    assert classify_employment_condition(Trend.RISING) is EmploymentCondition.WEAKENING
    assert classify_employment_condition(Trend.FLAT) is EmploymentCondition.STABLE


def test_classify_policy_stance() -> None:
    assert classify_policy_stance(Trend.RISING) is PolicyStance.HAWKISH
    assert classify_policy_stance(Trend.FALLING) is PolicyStance.DOVISH
    assert classify_policy_stance(Trend.FLAT) is PolicyStance.NEUTRAL


def test_classify_real_yield() -> None:
    assert classify_real_yield(2.0) is RealYieldLevel.HIGH
    assert classify_real_yield(0.5) is RealYieldLevel.LOW
    assert classify_real_yield(-1.0) is RealYieldLevel.NEGATIVE


def test_classify_dollar_condition() -> None:
    assert classify_dollar_condition(Trend.RISING) is DollarCondition.STRENGTHENING
    assert classify_dollar_condition(Trend.FALLING) is DollarCondition.WEAKENING
    assert classify_dollar_condition(Trend.FLAT) is DollarCondition.STABLE


def test_classify_macro_regime_reflation() -> None:
    regime = classify_macro_regime(
        InflationLevel.HIGH, Trend.RISING, EmploymentCondition.STRENGTHENING
    )
    assert regime is MacroRegime.REFLATION


def test_classify_macro_regime_stagflation() -> None:
    regime = classify_macro_regime(
        InflationLevel.HIGH, Trend.RISING, EmploymentCondition.WEAKENING
    )
    assert regime is MacroRegime.STAGFLATION


def test_classify_macro_regime_goldilocks() -> None:
    regime = classify_macro_regime(
        InflationLevel.LOW, Trend.FALLING, EmploymentCondition.STRENGTHENING
    )
    assert regime is MacroRegime.GOLDILOCKS


def test_classify_macro_regime_deflationary() -> None:
    regime = classify_macro_regime(
        InflationLevel.LOW, Trend.FALLING, EmploymentCondition.WEAKENING
    )
    assert regime is MacroRegime.DEFLATIONARY


def test_gold_score_strongly_bullish_scenario() -> None:
    """Negative real yields + high inflation + dovish Fed + weak USD => bullish for gold."""
    score = compute_gold_macro_score(
        RealYieldLevel.NEGATIVE, InflationLevel.HIGH, PolicyStance.DOVISH, DollarCondition.WEAKENING
    )
    assert score.total == 35 + 25 + 25 + 25
    assert score.bias is GoldBias.BULLISH


def test_gold_score_strongly_bearish_scenario() -> None:
    """High real yields + low inflation + hawkish Fed + strong USD => bearish for gold."""
    score = compute_gold_macro_score(
        RealYieldLevel.HIGH,
        InflationLevel.LOW,
        PolicyStance.HAWKISH,
        DollarCondition.STRENGTHENING,
    )
    assert score.total == -35 - 10 - 25 - 25
    assert score.bias is GoldBias.BEARISH


def test_gold_score_neutral_scenario() -> None:
    score = compute_gold_macro_score(
        RealYieldLevel.LOW, InflationLevel.MODERATE, PolicyStance.NEUTRAL, DollarCondition.STABLE
    )
    assert score.bias is GoldBias.NEUTRAL
