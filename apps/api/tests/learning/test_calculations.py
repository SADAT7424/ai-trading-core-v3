"""
Tests for the confidence calibration report. Constructs GroupedPerformance
objects directly with known win rates to make the expected verdict obvious.
"""
from app.learning.calculations import CalibrationVerdict, compute_calibration_report
from app.memory.calculations import GroupedPerformance
from app.performance.calculations import compute_performance_summary


def _group(grade: str, pnls: list[float]) -> GroupedPerformance:
    return GroupedPerformance(group=grade, summary=compute_performance_summary(pnls))


def test_insufficient_data_with_only_one_grade() -> None:
    groups = [_group("A", [100, 100, 100])]
    report = compute_calibration_report(groups)
    assert report.verdict is CalibrationVerdict.INSUFFICIENT_DATA


def test_insufficient_data_when_grade_has_too_few_trades() -> None:
    # A has enough trades, B only has 1 — below the min_trades_per_grade default of 3.
    groups = [_group("A", [100, 100, 100]), _group("B", [50])]
    report = compute_calibration_report(groups)
    assert report.verdict is CalibrationVerdict.INSUFFICIENT_DATA


def test_well_calibrated_when_win_rates_decrease_with_grade() -> None:
    # A: 3/3 wins (100%), B: 2/3 wins (~67%), C: 1/3 wins (~33%) — properly ordered.
    groups = [
        _group("A", [100, 100, 100]),
        _group("B", [100, 100, -50]),
        _group("C", [100, -50, -50]),
    ]
    report = compute_calibration_report(groups)
    assert report.verdict is CalibrationVerdict.WELL_CALIBRATED


def test_needs_attention_when_win_rates_are_inverted() -> None:
    # A performs WORSE than C — the grading is backwards.
    groups = [
        _group("A", [100, -50, -50]),  # 33% win rate
        _group("C", [100, 100, -50]),  # 67% win rate
    ]
    report = compute_calibration_report(groups)
    assert report.verdict is CalibrationVerdict.NEEDS_ATTENTION
    assert any("LOWER" in note for note in report.notes)


def test_missing_grades_are_simply_skipped_not_penalized() -> None:
    # No B or C data at all — should still compare A vs D directly.
    groups = [
        _group("A", [100, 100, 100]),
        _group("D", [-50, -50, -50]),
    ]
    report = compute_calibration_report(groups)
    assert report.verdict is CalibrationVerdict.WELL_CALIBRATED
    assert report.grades_with_data == 2
