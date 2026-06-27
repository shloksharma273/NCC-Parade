from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..models.api_models import DrillReport, ReportNotReadyResponse
from ..models.session_models import SessionStatus
from ..services.report_service import report_service
from ..services.session_service import session_service

router = APIRouter(prefix="/sessions", tags=["reports"])


@router.get("/{session_id}/report", response_model=DrillReport | ReportNotReadyResponse)
def get_report(session_id: str):
    session = session_service.get_session(session_id)
    current = SessionStatus(session["status"])

    if current != SessionStatus.REPORT_READY:
        return ReportNotReadyResponse(
            session_id=session_id,
            status=current.value,
            message="Report is not ready yet.",
        )

    report_path = session.get("report_path")
    if not report_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REPORT_NOT_FOUND", "message": "Report file not found."},
        )

    report = report_service.load_report(report_path)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "REPORT_NOT_FOUND", "message": "Report file not found."},
        )
    return report
