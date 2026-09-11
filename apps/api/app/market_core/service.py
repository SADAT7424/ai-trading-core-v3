"""
Market Core — service layer. Combines real ingested price bars
(repository.py) with pure indicator math and classification rules
(calculations.py) into one coherent market state snapshot.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.market_core.calculations import (
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
)
from app.market_core.repository import NoMarketDataError, get_recent_bars, to_calculation_bars

SMA_FAST_PERIOD = 20
SMA_SLOW_PERIOD = 50
ROC_PERIOD = 10
ATR_PERIOD = 14
RSI_PERIOD = 14

# Enough bars for the slowest indicator (SMA50) plus a little headroom.
MIN_BARS_REQUIRED = SMA_SLOW_PERIOD + 5


@dataclass
class MarketStateSnapshot:
    symbol: str
    interval: str
    as_of: datetime
    latest_close: float

    sma_fast: float
    sma_slow: float
    trend: Trend

    roc_pct: float
    momentum: Momentum

    atr: float
    atr_pct_of_price: float
    volatility: VolatilityLevel

    rsi: float
    rsi_condition: RsiCondition

    regime: MarketRegime


def compute_market_state(db: Session, symbol: str, interval: str) -> MarketStateSnapshot:
    rows = get_recent_bars(db, symbol, interval, limit=max(MIN_BARS_REQUIRED, ROC_PERIOD + 1) + 10)
    if len(rows) < MIN_BARS_REQUIRED:
        raise NoMarketDataError(symbol, interval)

    bars = to_calculation_bars(rows)
    closes = [b.close for b in bars]

    sma_fast = simple_moving_average(closes, SMA_FAST_PERIOD)
    sma_slow = simple_moving_average(closes, SMA_SLOW_PERIOD)
    roc_pct = rate_of_change(closes, ROC_PERIOD)
    atr = average_true_range(bars, ATR_PERIOD)
    rsi = relative_strength_index(closes, RSI_PERIOD)

    # MIN_BARS_REQUIRED guarantees these, but keep mypy honest about the
    # Optional return types from the pure calculation functions.
    assert sma_fast is not None
    assert sma_slow is not None
    assert roc_pct is not None
    assert atr is not None
    assert rsi is not None

    latest_close = closes[-1]
    atr_pct_of_price = (atr / latest_close) * 100 if latest_close else 0.0

    trend = classify_trend(sma_fast, sma_slow)
    momentum = classify_momentum(roc_pct)
    volatility = classify_volatility(atr_pct_of_price)
    rsi_condition = classify_rsi(rsi)
    regime = classify_regime(trend, volatility)

    return MarketStateSnapshot(
        symbol=symbol,
        interval=interval,
        as_of=rows[-1].bar_time,
        latest_close=latest_close,
        sma_fast=round(sma_fast, 4),
        sma_slow=round(sma_slow, 4),
        trend=trend,
        roc_pct=round(roc_pct, 3),
        momentum=momentum,
        atr=round(atr, 4),
        atr_pct_of_price=round(atr_pct_of_price, 3),
        volatility=volatility,
        rsi=round(rsi, 2),
        rsi_condition=rsi_condition,
        regime=regime,
    )
