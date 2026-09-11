"""
Market Core — pure calculations (Stage 4 in the master plan,
docs/RAH_OS_Master_Plan.docx section 6). Same discipline as
app/go_os/macro/calculations.py: pure functions, no database, no AI,
fully deterministic and independently unit-testable.

IMPORTANT — thresholds below are initial, reasonable starting points for
XAUUSD specifically, not empirically calibrated. Same caveat as the macro
engine: treat as defaults to replace once Stage 9 (Research) can backtest
them against real history.
"""
from dataclasses import dataclass
from enum import StrEnum


class Trend(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class Momentum(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    FLAT = "FLAT"


class VolatilityLevel(StrEnum):
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class RsiCondition(StrEnum):
    OVERBOUGHT = "OVERBOUGHT"
    OVERSOLD = "OVERSOLD"
    NEUTRAL = "NEUTRAL"


class MarketRegime(StrEnum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


@dataclass
class Bar:
    """Minimal OHLC shape the calculations need — decoupled from the ORM model."""

    open: float
    high: float
    low: float
    close: float


# --- Indicators ------------------------------------------------------------


def simple_moving_average(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def rate_of_change(closes: list[float], period: int) -> float | None:
    """% change between the latest close and the close `period` bars earlier."""
    if len(closes) < period + 1:
        return None
    reference = closes[-(period + 1)]
    if reference == 0:
        return None
    return ((closes[-1] - reference) / abs(reference)) * 100


def true_range(current: Bar, previous_close: float) -> float:
    return max(
        current.high - current.low,
        abs(current.high - previous_close),
        abs(current.low - previous_close),
    )


def average_true_range(bars: list[Bar], period: int) -> float | None:
    """Simple (non-Wilder-smoothed) average of True Range over `period` bars."""
    if len(bars) < period + 1:
        return None
    relevant = bars[-(period + 1):]
    true_ranges = [
        true_range(relevant[i], relevant[i - 1].close) for i in range(1, len(relevant))
    ]
    return sum(true_ranges) / len(true_ranges)


def relative_strength_index(closes: list[float], period: int = 14) -> float | None:
    """
    Standard Wilder-smoothed RSI. Returns a 0-100 value, or None if there
    isn't enough history yet. Uses Wilder's original smoothing (unlike
    average_true_range above, which deliberately uses a simple average) —
    this is the textbook RSI formula, and deviating from it would make the
    familiar 30/70 overbought/oversold thresholds meaningless.
    """
    if len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(c, 0.0) for c in changes]
    losses = [max(-c, 0.0) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# --- Thresholds (initial defaults — see module docstring) ------------------

_TREND_BAND_PCT = 0.15  # SMA20 vs SMA50 separation, as % of SMA50, to count as trending
_MOMENTUM_FLAT_BAND_PCT = 0.5  # ROC magnitude below this counts as flat
_VOLATILITY_HIGH_ATR_PCT = 1.5  # ATR as % of price
_VOLATILITY_LOW_ATR_PCT = 0.4
_RSI_OVERBOUGHT = 70.0
_RSI_OVERSOLD = 30.0


def classify_trend(sma_fast: float, sma_slow: float) -> Trend:
    if sma_slow == 0:
        return Trend.NEUTRAL
    separation_pct = ((sma_fast - sma_slow) / abs(sma_slow)) * 100
    if separation_pct > _TREND_BAND_PCT:
        return Trend.BULLISH
    if separation_pct < -_TREND_BAND_PCT:
        return Trend.BEARISH
    return Trend.NEUTRAL


def classify_momentum(roc_pct: float) -> Momentum:
    if roc_pct > _MOMENTUM_FLAT_BAND_PCT:
        return Momentum.POSITIVE
    if roc_pct < -_MOMENTUM_FLAT_BAND_PCT:
        return Momentum.NEGATIVE
    return Momentum.FLAT


def classify_volatility(atr_pct_of_price: float) -> VolatilityLevel:
    if atr_pct_of_price >= _VOLATILITY_HIGH_ATR_PCT:
        return VolatilityLevel.HIGH
    if atr_pct_of_price <= _VOLATILITY_LOW_ATR_PCT:
        return VolatilityLevel.LOW
    return VolatilityLevel.NORMAL


def classify_rsi(rsi: float) -> RsiCondition:
    if rsi >= _RSI_OVERBOUGHT:
        return RsiCondition.OVERBOUGHT
    if rsi <= _RSI_OVERSOLD:
        return RsiCondition.OVERSOLD
    return RsiCondition.NEUTRAL


def classify_regime(trend: Trend, volatility: VolatilityLevel) -> MarketRegime:
    """
    High volatility dominates the regime label regardless of trend, since it
    changes how positions should be sized and managed — a "trending" market
    with extreme volatility still needs to be flagged as such (see master
    plan section 9.5 on volatility management).
    """
    if volatility is VolatilityLevel.HIGH:
        return MarketRegime.HIGH_VOLATILITY
    if trend is not Trend.NEUTRAL:
        return MarketRegime.TRENDING
    return MarketRegime.RANGING
