"""
Unit tests for Trading Core's pure calculations. Expected values are
hand-computed — see the module docstring's discipline note, and the
verification session in the conversation history before these were written.
"""
from app.market_core.calculations import Momentum, Trend, VolatilityLevel
from app.trading_core.calculations import (
    Direction,
    QualityGrade,
    TradeClassification,
    classify_trade,
    compute_opportunity_score,
    detect_trend_pullback,
)


def test_detect_trend_pullback_long_setup() -> None:
    setup = detect_trend_pullback(
        Trend.BULLISH, Momentum.POSITIVE, latest_close=100.5, sma_fast=100.0
    )
    assert setup.direction is Direction.LONG
    assert setup.distance_to_fast_sma_pct == 0.5
    # closeness = 100 - (0.5/1.5)*100 = 66.67; *0.85 = 56.67; +15 momentum = 71.67
    assert setup.technical_score == 71.67


def test_detect_trend_pullback_short_setup() -> None:
    setup = detect_trend_pullback(
        Trend.BEARISH, Momentum.NEGATIVE, latest_close=99.5, sma_fast=100.0
    )
    assert setup.direction is Direction.SHORT
    assert setup.technical_score == 71.67  # symmetric to the long case


def test_detect_trend_pullback_no_setup_when_too_far_from_sma() -> None:
    # 5% above the fast SMA — well outside the 1.5% pullback band.
    setup = detect_trend_pullback(
        Trend.BULLISH, Momentum.POSITIVE, latest_close=105.0, sma_fast=100.0
    )
    assert setup.direction is Direction.NONE
    assert setup.technical_score == 0.0


def test_detect_trend_pullback_no_setup_when_momentum_opposes_trend() -> None:
    # Bullish trend but momentum has already turned negative — not a
    # pullback, a potential trend change. Should not fire a LONG setup.
    setup = detect_trend_pullback(
        Trend.BULLISH, Momentum.NEGATIVE, latest_close=100.2, sma_fast=100.0
    )
    assert setup.direction is Direction.NONE


def test_detect_trend_pullback_no_setup_when_ranging() -> None:
    setup = detect_trend_pullback(
        Trend.NEUTRAL, Momentum.FLAT, latest_close=100.0, sma_fast=100.0
    )
    assert setup.direction is Direction.NONE


def test_classify_trade_macro_aligned_long() -> None:
    assert classify_trade(Direction.LONG, gold_macro_score=40) is (
        TradeClassification.MACRO_ALIGNED_LONG
    )


def test_classify_trade_counter_macro_long() -> None:
    assert classify_trade(Direction.LONG, gold_macro_score=-40) is (
        TradeClassification.COUNTER_MACRO_LONG
    )


def test_classify_trade_macro_aligned_short() -> None:
    # Bearish macro score aligns with a SHORT setup.
    assert classify_trade(Direction.SHORT, gold_macro_score=-40) is (
        TradeClassification.MACRO_ALIGNED_SHORT
    )


def test_classify_trade_counter_macro_short() -> None:
    assert classify_trade(Direction.SHORT, gold_macro_score=40) is (
        TradeClassification.COUNTER_MACRO_SHORT
    )


def test_classify_trade_neutral_when_macro_score_small() -> None:
    assert classify_trade(Direction.LONG, gold_macro_score=5) is TradeClassification.MACRO_NEUTRAL
    assert classify_trade(Direction.NONE, gold_macro_score=40) is TradeClassification.MACRO_NEUTRAL


def test_opportunity_score_strong_aligned_setup_grades_a() -> None:
    score = compute_opportunity_score(
        Direction.LONG, technical_score=95.0, gold_macro_score=80, volatility=VolatilityLevel.NORMAL
    )
    assert score.quality is QualityGrade.A


def test_opportunity_score_weak_setup_grades_d() -> None:
    score = compute_opportunity_score(
        Direction.LONG,
        technical_score=20.0,
        gold_macro_score=-80,
        volatility=VolatilityLevel.NORMAL,
    )
    assert score.quality is QualityGrade.D


def test_opportunity_score_high_volatility_caps_quality() -> None:
    """
    Even a technically excellent, macro-aligned setup should not grade A (or
    even B) when volatility is HIGH — see calculations.py docstring on why.
    """
    score = compute_opportunity_score(
        Direction.LONG, technical_score=95.0, gold_macro_score=80, volatility=VolatilityLevel.HIGH
    )
    assert score.overall_score >= 80  # the raw score is still excellent...
    assert score.quality is QualityGrade.C  # ...but the grade is capped
