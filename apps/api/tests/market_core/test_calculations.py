"""
Unit tests for Market Core's pure calculations. All expected values are
hand-computed in comments — see the module docstring's discipline note.
"""
from app.market_core.calculations import (
    Bar,
    MarketRegime,
    Momentum,
    RsiCondition,
    Trend,
    VolatilityLevel,
    average_true_range,
    classify_momentum,
    classify_regime,
    classify_rsi,
    classify_trend,
    classify_volatility,
    rate_of_change,
    relative_strength_index,
    simple_moving_average,
    true_range,
)


def test_simple_moving_average() -> None:
    assert simple_moving_average([10, 20, 30], 3) == 20.0
    assert simple_moving_average([10, 20], 3) is None  # not enough data


def test_rate_of_change() -> None:
    assert rate_of_change([100, 100, 100, 110], 3) == 10.0
    assert rate_of_change([100, 90], 3) is None  # not enough data


def test_true_range_and_atr() -> None:
    bars = [
        Bar(open=10, high=12, low=9, close=11),
        Bar(open=11, high=15, low=10, close=14),  # TR = max(5, 4, 1) = 5
        Bar(open=14, high=14.5, low=13, close=13.5),  # TR = max(1.5, 0.5, 1) = 1.5
    ]
    assert true_range(bars[1], bars[0].close) == 5
    assert true_range(bars[2], bars[1].close) == 1.5
    assert average_true_range(bars, 2) == 3.25  # (5 + 1.5) / 2


def test_classify_trend() -> None:
    assert classify_trend(sma_fast=110, sma_slow=100) is Trend.BULLISH  # +10%
    assert classify_trend(sma_fast=90, sma_slow=100) is Trend.BEARISH  # -10%
    assert classify_trend(sma_fast=100.05, sma_slow=100) is Trend.NEUTRAL  # +0.05%


def test_classify_momentum() -> None:
    assert classify_momentum(2.0) is Momentum.POSITIVE
    assert classify_momentum(-2.0) is Momentum.NEGATIVE
    assert classify_momentum(0.1) is Momentum.FLAT


def test_classify_volatility() -> None:
    assert classify_volatility(2.0) is VolatilityLevel.HIGH
    assert classify_volatility(0.2) is VolatilityLevel.LOW
    assert classify_volatility(0.8) is VolatilityLevel.NORMAL


def test_classify_rsi() -> None:
    assert classify_rsi(75) is RsiCondition.OVERBOUGHT
    assert classify_rsi(25) is RsiCondition.OVERSOLD
    assert classify_rsi(50) is RsiCondition.NEUTRAL
    assert classify_rsi(70) is RsiCondition.OVERBOUGHT  # boundary
    assert classify_rsi(30) is RsiCondition.OVERSOLD  # boundary


def test_rsi_all_gains_is_100() -> None:
    closes = [100 + i for i in range(20)]
    assert relative_strength_index(closes, 14) == 100.0


def test_rsi_all_losses_is_0() -> None:
    closes = [100 - i for i in range(20)]
    assert relative_strength_index(closes, 14) == 0.0


def test_rsi_insufficient_data_returns_none() -> None:
    assert relative_strength_index([100, 101, 102], 14) is None


def test_classify_regime_high_volatility_dominates() -> None:
    # Even a clear bullish trend should be flagged HIGH_VOLATILITY, since
    # that changes position sizing/management regardless of direction.
    assert classify_regime(Trend.BULLISH, VolatilityLevel.HIGH) is MarketRegime.HIGH_VOLATILITY


def test_classify_regime_trending() -> None:
    assert classify_regime(Trend.BULLISH, VolatilityLevel.NORMAL) is MarketRegime.TRENDING
    assert classify_regime(Trend.BEARISH, VolatilityLevel.LOW) is MarketRegime.TRENDING


def test_classify_regime_ranging() -> None:
    assert classify_regime(Trend.NEUTRAL, VolatilityLevel.NORMAL) is MarketRegime.RANGING
    assert classify_regime(Trend.NEUTRAL, VolatilityLevel.LOW) is MarketRegime.RANGING
