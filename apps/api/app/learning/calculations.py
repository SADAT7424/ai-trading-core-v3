"""
Learning — pure calculations (Stage 11 in the master plan, section 13.9:
"Confidence Calibration"). Adapted from "if the model reports 90%
confidence, comparable predictions should be correct ~90% of the time" to
this system's actual output: quality grades A-D should have DECREASING win
rates, in order — if D-graded setups win more often than A-graded ones,
the scoring rubric itself (app/trading_core/calculations.py) is measuring
the wrong things and needs revisiting, not just "more data."

Scope note: this is the genuinely checkable subset of calibration right
now. Champion/challenger model comparison (section 13.8) and formal concept
drift detection (section 13.9) need multiple competing model versions and a
long time series to be meaningful — building them today, with one strategy
and a handful of trades, would be the same premature-infrastructure trap
flagged in app/memory/calculations.py.
"""
from dataclasses import dataclass
from enum import StrEnum

from app.memory.calculations import GroupedPerformance

_GRADE_ORDER = ["A", "B", "C", "D"]  # best to worst


class CalibrationVerdict(StrEnum):
    WELL_CALIBRATED = "WELL_CALIBRATED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class CalibrationReport:
    verdict: CalibrationVerdict
    notes: list[str]
    grades_with_data: int


def compute_calibration_report(
    grouped_by_grade: list[GroupedPerformance], min_trades_per_grade: int = 3
) -> CalibrationReport:
    by_grade = {g.group: g.summary for g in grouped_by_grade}
    graded = [
        (grade, by_grade[grade])
        for grade in _GRADE_ORDER
        if grade in by_grade and by_grade[grade].total_trades >= min_trades_per_grade
    ]

    if len(graded) < 2:
        return CalibrationReport(
            verdict=CalibrationVerdict.INSUFFICIENT_DATA,
            notes=[
                f"Need at least 2 grades with {min_trades_per_grade}+ closed trades each to "
                f"check calibration — only have {len(graded)} so far. This is expected early "
                f"on; keep paper trading and check again later."
            ],
            grades_with_data=len(graded),
        )

    notes: list[str] = []
    inverted = False
    for (grade_a, summary_a), (grade_b, summary_b) in zip(graded, graded[1:], strict=False):
        if summary_a.win_rate_pct < summary_b.win_rate_pct:
            inverted = True
            notes.append(
                f"Grade {grade_a} win rate ({summary_a.win_rate_pct}%) is LOWER than "
                f"grade {grade_b} ({summary_b.win_rate_pct}%) — the opposite of what a "
                f"quality grade should mean."
            )

    if not notes:
        notes.append(
            "Win rates decrease as grade gets worse, as expected — the quality "
            "score is (so far) doing what it's supposed to."
        )

    verdict = (
        CalibrationVerdict.NEEDS_ATTENTION if inverted else CalibrationVerdict.WELL_CALIBRATED
    )
    return CalibrationReport(
        verdict=verdict,
        notes=notes,
        grades_with_data=len(graded),
    )
