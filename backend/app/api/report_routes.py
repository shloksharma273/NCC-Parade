from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

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


@router.get("/{session_id}/report/pdf")
def download_report_pdf(session_id: str) -> FileResponse:
    session = session_service.get_session(session_id)
    current = SessionStatus(session["status"])

    if current != SessionStatus.REPORT_READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "REPORT_NOT_READY", "message": "Report is not ready yet."},
        )

    report_path = session.get("report_path")
    report = report_service.load_report(report_path) if report_path else None
    pdf_path = report_service.resolve_pdf_path(session_id, report)
    if pdf_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "REPORT_PDF_NOT_FOUND",
                "message": "PDF report is not available for this drill type or session.",
            },
        )

    filename = report_service.report_pdf_filename(session, report)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
