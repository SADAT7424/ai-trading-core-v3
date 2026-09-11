"""
Macro Regime Engine — service layer. Combines real ingested data
(repository.py) with pure classification rules (calculations.py) into one
coherent snapshot of current macro conditions.

Series codes used (all from FRED, ingested in Stage 2):
- CPIAUCSL: headline CPI -> inflation level/trend
- UNRATE: unemployment rate -> employment condition
- FEDFUNDS: effective federal funds rate -> policy stance
- DGS10: 10-Year Treasury yield -> real yield proxy (see caveat below)
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.go_os.macro.calculations import (
    EmploymentCondition,
    GoldScoreBreakdown,
    InflationLevel,
    MacroRegime,
    PolicyStance,
    RealYieldLevel,
    Trend,
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
TREASURY_10Y_SERIES = "DGS10"


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

    real_yield_proxy_pct: float
    real_yield_level: RealYieldLevel
    real_yield_caveat: str

    regime: MacroRegime
    gold_score: GoldScoreBreakdown


def compute_macro_regime_snapshot(db: Session) -> MacroRegimeSnapshot:
    inflation_result = get_year_over_year_change(db, CPI_SERIES)
    if inflation_result is None:
        raise ValueError(
            f"Not enough {CPI_SERIES} history to compute a year-over-year change yet."
        )
    cpi_point, inflation_yoy_pct = inflation_result
    # CPI trend: is inflation itself accelerating? Approximate with the
    # change in YoY inflation over the last ~90 days as a simple proxy.
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

    treasury_result = get_recent_trend_change(db, TREASURY_10Y_SERIES, lookback_days=30)
    if treasury_result is None:
        raise ValueError(f"Not enough {TREASURY_10Y_SERIES} history yet.")
    treasury_point, _treasury_change = treasury_result

    # Real yield proxy: nominal 10Y yield minus REALIZED (trailing) CPI
    # inflation. The master plan's actual Real-Yield Engine (section 5.4)
    # uses market-implied breakeven inflation expectations (from TIPS),
    # which is more forward-looking and more correct — we don't ingest TIPS
    # breakevens yet, so this is a deliberate, documented simplification.
    real_yield_proxy_pct = treasury_point.value - inflation_yoy_pct
    real_yield_caveat = (
        "Approximated as nominal 10Y yield minus trailing YoY CPI inflation, "
        "not true market-implied breakeven inflation expectations (TIPS not "
        "yet ingested). Treat as directional, not precise."
    )

    inflation_level = classify_inflation_level(inflation_yoy_pct)
    employment_condition = classify_employment_condition(unemployment_trend)
    policy_stance = classify_policy_stance(fed_funds_trend)
    real_yield_level = classify_real_yield(real_yield_proxy_pct)

    regime = classify_macro_regime(inflation_level, inflation_trend, employment_condition)
    gold_score = compute_gold_macro_score(real_yield_level, inflation_level, policy_stance)

    as_of = max(
        cpi_point.observation_date,
        unemployment_point.observation_date,
        fed_funds_point.observation_date,
        treasury_point.observation_date,
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
        real_yield_proxy_pct=round(real_yield_proxy_pct, 2),
        real_yield_level=real_yield_level,
        real_yield_caveat=real_yield_caveat,
        regime=regime,
        gold_score=gold_score,
    )
