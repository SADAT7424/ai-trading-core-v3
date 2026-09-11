"""
Tests for Memory module calculations. Uses hand-constructed trade records
where the expected grouping/filtering is obvious.
"""
from app.memory.calculations import (
    breakdown_by_classification,
    breakdown_by_quality_grade,
    find_similar_historical_setups,
)
from app.memory.repository import ClosedTradeRecord


def _record(classification: str, grade: str, macro_score: int, pnl: float) -> ClosedTradeRecord:
    return ClosedTradeRecord(
        classification=classification,
        quality_grade=grade,
        entry_gold_macro_score=macro_score,
        realized_pnl=pnl,
        r_multiple=pnl / 100,
    )


def test_breakdown_by_classification_groups_correctly() -> None:
    records = [
        _record("MACRO_ALIGNED_LONG", "B", 50, 100),
        _record("MACRO_ALIGNED_LONG", "B", 60, 50),
        _record("COUNTER_MACRO_LONG", "C", -40, -30),
    ]
    breakdown = breakdown_by_classification(records)
    groups = {g.group: g.summary for g in breakdown}

    assert groups["MACRO_ALIGNED_LONG"].total_trades == 2
    assert groups["MACRO_ALIGNED_LONG"].total_realized_pnl == 150
    assert groups["COUNTER_MACRO_LONG"].total_trades == 1
    assert groups["COUNTER_MACRO_LONG"].total_realized_pnl == -30


def test_breakdown_handles_missing_classification() -> None:
    records = [_record(None, "B", 50, 100)]  # type: ignore[arg-type]
    breakdown = breakdown_by_classification(records)
    assert breakdown[0].group == "UNCLASSIFIED"


def test_breakdown_by_quality_grade() -> None:
    records = [
        _record("MACRO_ALIGNED_LONG", "A", 50, 100),
        _record("MACRO_ALIGNED_LONG", "A", 60, 120),
        _record("MACRO_ALIGNED_LONG", "D", 10, -80),
    ]
    breakdown = breakdown_by_quality_grade(records)
    groups = {g.group: g.summary for g in breakdown}

    assert groups["A"].win_rate_pct == 100.0
    assert groups["D"].win_rate_pct == 0.0


def test_find_similar_setups_filters_by_classification_and_score_tolerance() -> None:
    records = [
        _record("MACRO_ALIGNED_LONG", "B", 50, 100),  # similar: same class, score close
        _record("MACRO_ALIGNED_LONG", "B", 45, 80),  # similar: within tolerance
        _record("MACRO_ALIGNED_LONG", "B", 10, -50),  # NOT similar: score too far (delta 40)
        _record("COUNTER_MACRO_LONG", "C", 50, -30),  # NOT similar: wrong classification
    ]
    result = find_similar_historical_setups(
        records,
        current_gold_macro_score=50,
        current_classification="MACRO_ALIGNED_LONG",
        tolerance=20,
    )
    assert result.similar_trade_count == 2
    assert result.similar_trades_summary.total_realized_pnl == 180


def test_find_similar_setups_returns_zero_count_when_no_history() -> None:
    result = find_similar_historical_setups(
        [], current_gold_macro_score=50, current_classification="MACRO_ALIGNED_LONG"
    )
    assert result.similar_trade_count == 0
    assert result.similar_trades_summary.total_trades == 0
