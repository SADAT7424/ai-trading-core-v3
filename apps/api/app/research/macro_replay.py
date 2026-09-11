"""
Point-in-time macro replay for backtesting.

Reuses the EXACT SAME classification functions as the live Macro Regime
Engine (app/go_os/macro/calculations.py) — the only difference is where the
numbers come from: here, from pre-fetched historical point-in-time vintages
instead of a live "give me the latest" query. This is what makes the
backtest genuinely free of look-ahead bias: on backtest day D, only
observations with realtime_start <= D <= realtime_end are visible, exactly
matching what /api/v1/economic/.../as-of/{date} already proved out in
Stage 2.

Scope note: this computes only what Trading Core's classify_trade() and
compute_gold_macro_score() actually consume (real yield, inflation level,
policy stance, USD condition) — it does not reconstruct the full 4-quadrant
macro regime label (Reflation/Stagflation/etc.), which isn't needed for
backtesting trade classification and isn't used by any scoring function.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from app.go_os.macro.calculations import (
    classify_dollar_condition,
    classify_inflation_level,
    classify_policy_stance,
    classify_real_yield,
    compute_gold_macro_score,
)
from app.go_os.macro.calculations import classify_trend as classify_macro_trend
from app.research.data_types import EconomicPoint

CPI_SERIES = "CPIAUCSL"
FED_FUNDS_SERIES = "FEDFUNDS"
REAL_YIELD_SERIES = "DFII10"
USD_INDEX_SERIES = "DTWEXBGS"


def _value_known_as_of(points: list[EconomicPoint], as_of: date) -> tuple[date, float] | None:
    """The most recent observation whose vintage was already known by `as_of`."""
    candidates = [p for p in points if p.realtime_start <= as_of <= p.realtime_end]
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.observation_date)
    return latest.observation_date, latest.value


def _value_near_date_as_of(
    points: list[EconomicPoint], as_of: date, target_date: date, tolerance_days: int = 45
) -> float | None:
    """Same idea as go_os/macro/repository.py's get_point_near, but point-in-time constrained."""
    candidates = [p for p in points if p.realtime_start <= as_of <= p.realtime_end]
    if not candidates:
        return None
    closest = min(candidates, key=lambda p: abs((p.observation_date - target_date).days))
    if abs((closest.observation_date - target_date).days) > tolerance_days:
        return None
    return closest.value


@dataclass
class MacroReplaySnapshot:
    gold_macro_score: int


def compute_macro_snapshot_as_of(
    series_points: dict[str, list[EconomicPoint]], as_of: date
) -> MacroReplaySnapshot | None:
    """
    Returns None (not an error) when there isn't enough point-in-time history
    yet to compute a snapshot — the backtest loop treats this exactly like
    "no macro data" and skips the day, the same way the live system would
    return a 400 rather than fabricate a number.
    """
    cpi_points = series_points.get(CPI_SERIES, [])
    latest_cpi = _value_known_as_of(cpi_points, as_of)
    if latest_cpi is None:
        return None
    latest_cpi_date, latest_cpi_value = latest_cpi
    year_ago_cpi = _value_near_date_as_of(cpi_points, as_of, latest_cpi_date - timedelta(days=365))
    if year_ago_cpi is None or year_ago_cpi == 0:
        return None
    inflation_yoy_pct = ((latest_cpi_value - year_ago_cpi) / abs(year_ago_cpi)) * 100

    fed_points = series_points.get(FED_FUNDS_SERIES, [])
    latest_fed = _value_known_as_of(fed_points, as_of)
    if latest_fed is None:
        return None
    fed_date, fed_value = latest_fed
    fed_prior = _value_near_date_as_of(fed_points, as_of, fed_date - timedelta(days=180))
    fed_change = (fed_value - fed_prior) if fed_prior is not None else 0.0
    policy_stance = classify_policy_stance(classify_macro_trend(fed_change, flat_band=0.1))

    real_yield_points = series_points.get(REAL_YIELD_SERIES, [])
    latest_real_yield = _value_known_as_of(real_yield_points, as_of)
    if latest_real_yield is None:
        return None
    _, real_yield_value = latest_real_yield

    usd_points = series_points.get(USD_INDEX_SERIES, [])
    latest_usd = _value_known_as_of(usd_points, as_of)
    if latest_usd is None:
        return None
    usd_date, usd_value = latest_usd
    usd_prior = _value_near_date_as_of(usd_points, as_of, usd_date - timedelta(days=90))
    usd_change = (usd_value - usd_prior) if usd_prior is not None else 0.0
    usd_condition = classify_dollar_condition(classify_macro_trend(usd_change, flat_band=0.5))

    inflation_level = classify_inflation_level(inflation_yoy_pct)
    real_yield_level = classify_real_yield(real_yield_value)

    gold_score = compute_gold_macro_score(
        real_yield_level, inflation_level, policy_stance, usd_condition
    )

    return MacroReplaySnapshot(gold_macro_score=gold_score.total)
