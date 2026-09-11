"""
/api/v1/learning — confidence calibration check. Computed fresh from
existing closed positions grouped by entry quality grade.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.learning.calculations import CalibrationVerdict, compute_calibration_report
from app.memory.calculations import breakdown_by_quality_grade
from app.memory.repository import get_closed_trade_records

router = APIRouter(prefix="/learning", tags=["learning"])


class CalibrationReportResponse(BaseModel):
    verdict: CalibrationVerdict
    notes: list[str]
    grades_with_data: int


@router.get("/calibration", response_model=CalibrationReportResponse)
def get_calibration_report(
    symbol: str | None = None, db: Session = Depends(get_db)
) -> CalibrationReportResponse:
    records = get_closed_trade_records(db, symbol)
    grouped = breakdown_by_quality_grade(records)
    report = compute_calibration_report(grouped)
    return CalibrationReportResponse(
        verdict=report.verdict, notes=report.notes, grades_with_data=report.grades_with_data
    )
