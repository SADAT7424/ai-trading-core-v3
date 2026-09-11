"""
Macro Regime Engine — service layer. Combines real ingested data
(repository.py) with pure classification rules (calculations.py) into one
coherent snapshot of current macro conditions.

Series codes used (all from FRED, ingested in Stage 2):
- CPIAUCSL: headline CPI -> realized inflation level/trend
- UNRATE: unemployment rate -> employment condition
- FEDFUNDS: effective federal funds rate -> policy stance
- DFII10: 10-Year TIPS yield -> real yield, DIRECTLY market-priced (this
  replaced an earlier nominal-minus-trailing-CPI approximation once we
  confirmed FRED actually publishes the real thing for free)
- T10YIE: 10-Year breakeven inflation rate -> forward-looking inflation
  expectations, shown for context (see caveat below)
- DTWEXBGS: Trade-weighted broad USD index -> dollar strength/weakness,
  gold's most frequently cited driver in the master plan
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.go_os.macro.calculations import (
    DollarCondition,
    EmploymentCondition,
    GoldScoreBreakdown,
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
from app.go_os.macro.repository import (
    get_recent_trend_change,
    get_year_over_year_change,
)

CPI_SERIES = "CPIAUCSL"
UNEMPLOYMENT_SERIES = "UNRATE"
FED_FUNDS_SERIES = "FEDFUNDS"
REAL_YIELD_10Y_SERIES = "DFII10"
BREAKEVEN_INFLATION_10Y_SERIES = "T10YIE"
USD_INDEX_SERIES = "DTWEXBGS"


@dataclass
class MacroRegimeSnapshot:
    as_of: date

    inflation_yoy_pct: float
    inflation_level: InflationLevel
    inflation_trend: Trend

    unemployment_rate_pct: float
    employment_condition: EmploymentCondition

    fed_funds_rate_pct: float
    policy_stance: PolicyStance

    real_yield_10y_pct: float
    real_yield_level: RealYieldLevel

    breakeven_inflation_10y_pct: float
    breakeven_inflation_note: str

    usd_index_level: float
    usd_condition: DollarCondition

    regime: MacroRegime
    gold_score: GoldScoreBreakdown


def compute_macro_regime_snapshot(db: Session) -> MacroRegimeSnapshot:
    inflation_result = get_year_over_year_change(db, CPI_SERIES)
    if inflation_result is None:
        raise ValueError(
            f"Not enough {CPI_SERIES} history to compute a year-over-year change yet."
        )
    cpi_point, inflation_yoy_pct = inflation_result
    # CPI trend: is realized inflation itself accelerating? Approximate with
    # the change in YoY inflation over the last ~90 days.
    inflation_trend_result = get_recent_trend_change(db, CPI_SERIES, lookback_days=90)
    inflation_trend = (
        classify_trend(inflation_trend_result[1], flat_band=0.5)
        if inflation_trend_result
        else Trend.FLAT
    )

    unemployment_result = get_recent_trend_change(db, UNEMPLOYMENT_SERIES)
    if unemployment_result is None:
        raise ValueError(f"Not enough {UNEMPLOYMENT_SERIES} history yet.")
    unemployment_point, unemployment_change = unemployment_result
    unemployment_trend = classify_trend(unemployment_change, flat_band=0.1)

    fed_funds_result = get_recent_trend_change(db, FED_FUNDS_SERIES)
    if fed_funds_result is None:
        raise ValueError(f"Not enough {FED_FUNDS_SERIES} history yet.")
    fed_funds_point, fed_funds_change = fed_funds_result
    fed_funds_trend = classify_trend(fed_funds_change, flat_band=0.1)

    # Real yield: DFII10 is the market-priced 10-Year TIPS yield — this IS
    # the real yield directly, not an approximation. No caveat needed here
    # anymore (see module docstring for what this replaced).
    real_yield_result = get_recent_trend_change(db, REAL_YIELD_10Y_SERIES, lookback_days=30)
    if real_yield_result is None:
        raise ValueError(f"Not enough {REAL_YIELD_10Y_SERIES} history yet.")
    real_yield_point, _real_yield_change = real_yield_result

    breakeven_result = get_recent_trend_change(
        db, BREAKEVEN_INFLATION_10Y_SERIES, lookback_days=30
    )
    if breakeven_result is None:
        raise ValueError(f"Not enough {BREAKEVEN_INFLATION_10Y_SERIES} history yet.")
    breakeven_point, _breakeven_change = breakeven_result
    breakeven_inflation_note = (
        "Market-implied forward-looking inflation expectation (10Y breakeven), "
        "shown for context alongside realized CPI. Not yet incorporated into "
        "the regime classification or gold score below — a natural Stage 3 "
        "follow-up would be scoring the divergence between this and realized "
        "CPI (expectations rising faster than realized inflation is itself "
        "informative)."
    )

    usd_result = get_recent_trend_change(db, USD_INDEX_SERIES, lookback_days=90)
    if usd_result is None:
        raise ValueError(f"Not enough {USD_INDEX_SERIES} history yet.")
    usd_point, usd_change = usd_result
    usd_trend = classify_trend(usd_change, flat_band=0.5)

    inflation_level = classify_inflation_level(inflation_yoy_pct)
    employment_condition = classify_employment_condition(unemployment_trend)
    policy_stance = classify_policy_stance(fed_funds_trend)
    real_yield_level = classify_real_yield(real_yield_point.value)
    usd_condition = classify_dollar_condition(usd_trend)

    regime = classify_macro_regime(inflation_level, inflation_trend, employment_condition)
    gold_score = compute_gold_macro_score(
        real_yield_level, inflation_level, policy_stance, usd_condition
    )

    as_of = max(
        cpi_point.observation_date,
        unemployment_point.observation_date,
        fed_funds_point.observation_date,
        real_yield_point.observation_date,
        breakeven_point.observation_date,
        usd_point.observation_date,
    )

    return MacroRegimeSnapshot(
        as_of=as_of,
        inflation_yoy_pct=round(inflation_yoy_pct, 2),
        inflation_level=inflation_level,
        inflation_trend=inflation_trend,
        unemployment_rate_pct=unemployment_point.value,
        employment_condition=employment_condition,
        fed_funds_rate_pct=fed_funds_point.value,
        policy_stance=policy_stance,
        real_yield_10y_pct=real_yield_point.value,
        real_yield_level=real_yield_level,
        breakeven_inflation_10y_pct=breakeven_point.value,
        breakeven_inflation_note=breakeven_inflation_note,
        usd_index_level=usd_point.value,
        usd_condition=usd_condition,
        regime=regime,
        gold_score=gold_score,
    )
