"""
Tests for the backtest engine. Uses hand-constructed synthetic price/macro
data where the correct outcome can be reasoned about directly, rather than
trusting the engine's own output.
"""
from datetime import date, timedelta

from app.research.backtest import TradeExitReason, run_backtest
from app.research.data_types import EconomicPoint, PriceBar
from app.trading_core.calculations import Direction, TradeClassification


def _flat_econ_series(as_of_from: date) -> dict[str, list[EconomicPoint]]:
    """A minimal, strongly-bullish-for-gold macro backdrop, known from day one."""
    far_past = as_of_from - timedelta(days=730)
    return {
        "CPIAUCSL": [
            EconomicPoint(far_past - timedelta(days=365), 300.0, far_past, date(9999, 12, 31)),
            EconomicPoint(far_past, 320.0, far_past, date(9999, 12, 31)),  # +6.7% YoY -> HIGH
        ],
        "FEDFUNDS": [
            EconomicPoint(far_past - timedelta(days=180), 5.0, far_past, date(9999, 12, 31)),
            EconomicPoint(far_past, 4.0, far_past, date(9999, 12, 31)),  # cutting -> DOVISH
        ],
        "DFII10": [
            EconomicPoint(far_past, -0.5, far_past, date(9999, 12, 31)),  # NEGATIVE
        ],
        "DTWEXBGS": [
            EconomicPoint(far_past - timedelta(days=90), 122.0, far_past, date(9999, 12, 31)),
            EconomicPoint(far_past, 118.0, far_past, date(9999, 12, 31)),  # WEAKENING
        ],
    }


def _bar(d: date, o: float, h: float, low: float, c: float) -> PriceBar:
    return PriceBar(bar_date=d, open=o, high=h, low=low, close=c)


def test_no_trades_when_insufficient_bars() -> None:
    bars = [_bar(date(2024, 1, 1) + timedelta(days=i), 100, 101, 99, 100) for i in range(10)]
    result = run_backtest(bars, {})
    assert result.trades == []


def test_skips_days_with_no_macro_data() -> None:
    start = date(2024, 1, 1)
    # 60 flat bars, plenty of price history, but NO economic series at all.
    bars = [_bar(start + timedelta(days=i), 100, 101, 99, 100) for i in range(60)]
    result = run_backtest(bars, {})
    assert result.trades == []
    assert result.days_skipped_no_macro_data > 0


def test_clean_bullish_pullback_hits_target() -> None:
    start = date(2024, 1, 1)
    bars = []
    price = 3000.0
    # 55 bars of a steady, low-volatility uptrend to build a clean bullish
    # SMA20/SMA50 and a small ATR.
    for i in range(55):
        price += 3.0
        bars.append(_bar(start + timedelta(days=i), price - 0.5, price + 1, price - 1, price))

    # Pull back toward the fast SMA without breaking momentum negative.
    pullback_price = price - 2.0
    bars.append(
        _bar(start + timedelta(days=55), price, price + 0.5, pullback_price - 1, pullback_price)
    )

    # Then rally hard, well past any reasonable 2R target, guaranteeing a
    # TAKE_PROFIT exit rather than an ambiguous outcome.
    rally_price = pullback_price + 200.0
    bars.append(
        _bar(
            start + timedelta(days=56),
            pullback_price,
            rally_price + 5,
            pullback_price - 1,
            rally_price,
        )
    )

    econ = _flat_econ_series(start)
    result = run_backtest(bars, econ)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.direction is Direction.LONG
    assert trade.classification is TradeClassification.MACRO_ALIGNED_LONG
    assert trade.exit_reason is TradeExitReason.TAKE_PROFIT
    assert trade.r_multiple > 0


def test_clean_bullish_pullback_hits_stop_instead() -> None:
    start = date(2024, 1, 1)
    bars = []
    price = 3000.0
    for i in range(55):
        price += 3.0
        bars.append(_bar(start + timedelta(days=i), price - 0.5, price + 1, price - 1, price))

    pullback_price = price - 2.0
    bars.append(
        _bar(start + timedelta(days=55), price, price + 0.5, pullback_price - 1, pullback_price)
    )

    # Instead of rallying, price collapses well past any reasonable stop.
    crash_price = pullback_price - 200.0
    bars.append(
        _bar(
            start + timedelta(days=56),
            pullback_price,
            pullback_price + 1,
            crash_price - 5,
            crash_price,
        )
    )

    econ = _flat_econ_series(start)
    result = run_backtest(bars, econ)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason is TradeExitReason.STOP_LOSS
    assert trade.r_multiple < 0
    # A stop-loss exit at exactly the stop price should be almost exactly
    # -1R by construction (entry risk = 1R, exit at the stop = -1R).
    assert -1.1 <= trade.r_multiple <= -0.9


def test_no_overlapping_trades() -> None:
    """
    After a trade closes, the scan must resume AFTER it, not re-signal on
    bars that were already inside the completed trade's window.
    """
    start = date(2024, 1, 1)
    bars = []
    price = 3000.0
    for i in range(55):
        price += 3.0
        bars.append(_bar(start + timedelta(days=i), price - 0.5, price + 1, price - 1, price))
    pullback_price = price - 2.0
    bars.append(
        _bar(start + timedelta(days=55), price, price + 0.5, pullback_price - 1, pullback_price)
    )
    rally_price = pullback_price + 200.0
    bars.append(
        _bar(
            start + timedelta(days=56),
            pullback_price,
            rally_price + 5,
            pullback_price - 1,
            rally_price,
        )
    )
    # A few more quiet bars after the big rally.
    for i in range(57, 62):
        d = start + timedelta(days=i)
        bars.append(_bar(d, rally_price, rally_price + 1, rally_price - 1, rally_price))

    econ = _flat_econ_series(start)
    result = run_backtest(bars, econ)

    # Entry/exit windows must never overlap.
    for a, b in zip(result.trades, result.trades[1:], strict=False):
        assert a.exit_date <= b.entry_date


def test_still_open_trade_excluded_from_clean_exit_reasons() -> None:
    start = date(2024, 1, 1)
    bars = []
    price = 3000.0
    for i in range(55):
        price += 3.0
        bars.append(_bar(start + timedelta(days=i), price - 0.5, price + 1, price - 1, price))
    pullback_price = price - 2.0
    bars.append(
        _bar(start + timedelta(days=55), price, price + 0.5, pullback_price - 1, pullback_price)
    )
    # Data ends immediately — no bar ever hits stop or target.
    econ = _flat_econ_series(start)
    result = run_backtest(bars, econ)

    if result.trades:
        assert result.trades[-1].exit_reason is TradeExitReason.STILL_OPEN
