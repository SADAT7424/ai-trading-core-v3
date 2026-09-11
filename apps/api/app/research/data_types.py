"""
Shared data types for the Research/Backtesting engine (Stage 9,
docs/RAH_OS_Master_Plan.docx section 13.4).

These are deliberately plain dataclasses, decoupled from the ORM — the
backtest engine takes pre-fetched lists of these, not database sessions, so
its core logic stays pure and testable with synthetic data (same discipline
as every calculations.py module so far).
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class EconomicPoint:
    """One point-in-time vintage of one economic observation."""

    observation_date: date
    value: float
    realtime_start: date
    realtime_end: date


@dataclass
class PriceBar:
    bar_date: date
    open: float
    high: float
    low: float
    close: float
