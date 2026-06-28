from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from ..config import FRAMES_MEDIA_DIR
from ..models.api_models import InstructorDecisionRequest, InstructorDecisionResponse
from ..services.camera_service import camera_service
from ..services.session_service import session_service
from ..utils.time_utils import utc_now_iso

router = APIRouter(prefix="/sessions", tags=["decisions"])


@router.post("/{session_id}/decision", response_model=InstructorDecisionResponse)
def save_instructor_decision(session_id: str, request: InstructorDecisionRequest) -> InstructorDecisionResponse:
    session = session_service.get_session(session_id)
    if session["status"] != "REPORT_READY":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "INVALID_SESSION_STATE", "message": "Decision can only be saved for completed reports."},
        )

    ai_result = session.get("ai_result") or session.get("result")
    if request.decision != "accept_ai" and not (request.remarks or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "REMARKS_REQUIRED", "message": "Remarks are required when overriding the AI result."},
        )

    instructor_decision = ai_result if request.decision == "accept_ai" else request.decision
    final_result = instructor_decision
    remarks = request.remarks if request.decision != "accept_ai" else request.remarks

    session_service.sessions.update_session(
        session_id,
        instructor_decision=instructor_decision,
        instructor_remarks=remarks,
        decision_at=utc_now_iso(),
        final_result=final_result,
        result=final_result,
    )

    return InstructorDecisionResponse(
        session_id=session_id,
        ai_result=ai_result,
        instructor_decision=instructor_decision,
        final_result=final_result,
        remarks=remarks,
        message="Decision saved successfully.",
    )


@router.get("/{session_id}/decision", response_model=InstructorDecisionResponse)
def get_instructor_decision(session_id: str) -> InstructorDecisionResponse:
    session = session_service.get_session(session_id)
    ai_result = session.get("ai_result") or session.get("result")
    instructor_decision = session.get("instructor_decision")
    if not instructor_decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DECISION_NOT_FOUND", "message": "No instructor decision saved yet."},
        )
    return InstructorDecisionResponse(
        session_id=session_id,
        ai_result=ai_result,
        instructor_decision=instructor_decision,
        final_result=session.get("final_result") or instructor_decision,
        remarks=session.get("instructor_remarks"),
        message="Decision loaded.",
    )


@router.get("/{session_id}/attempts")
def session_attempts(session_id: str) -> dict:
    session = session_service.get_session(session_id)
    cadet_id = session.get("cadet_id")
    drill_type = session["drill_type"]
    if not cadet_id:
        return {"session_id": session_id, "attempts": [session_service.get_session(session_id)]}
    attempts = session_service.list_sessions(limit=50, drill_type=drill_type, cadet_id=cadet_id)
    return {"cadet_id": cadet_id, "drill_type": drill_type, "attempts": attempts}
