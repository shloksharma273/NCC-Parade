from __future__ import annotations

from fastapi import APIRouter, Query

from ..models.api_models import (
    CreateSessionRequest,
    CreateSessionResponse,
    SessionListResponse,
    SessionResponse,
)
from ..services.session_service import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _to_session_response(session: dict) -> SessionResponse:
    return SessionResponse(
        session_id=session["session_id"],
        cadet_id=session.get("cadet_id"),
        cadet_name=session["cadet_name"],
        squad=session.get("squad"),
        unit=session.get("unit"),
        drill_type=session["drill_type"],
        attempt_number=session["attempt_number"],
        camera_id=session["camera_id"],
        camera_view=session.get("camera_view"),
        status=session["status"],
        created_at=session["created_at"],
        started_at=session.get("started_at"),
        stopped_at=session.get("stopped_at"),
        video_path=session.get("video_path"),
        report_path=session.get("report_path"),
        score=session.get("score"),
        result=session.get("result"),
        ai_result=session.get("ai_result"),
        instructor_decision=session.get("instructor_decision"),
        instructor_remarks=session.get("instructor_remarks"),
        decision_at=session.get("decision_at"),
        final_result=session.get("final_result"),
        error_message=session.get("error_message"),
    )


@router.post("", response_model=CreateSessionResponse)
def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
    session = session_service.create_session(request)
    return CreateSessionResponse(
        session_id=session["session_id"],
        status=session["status"],
        message="Session created successfully.",
    )


@router.get("", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    drill_type: str | None = None,
    cadet_id: str | None = None,
) -> SessionListResponse:
    sessions = session_service.list_sessions(limit=limit, drill_type=drill_type, cadet_id=cadet_id)
    return SessionListResponse(
        sessions=[
            {
                "session_id": s["session_id"],
                "cadet_name": s["cadet_name"],
                "drill_type": s["drill_type"],
                "attempt_number": s["attempt_number"],
                "status": s["status"],
                "score": s.get("score"),
                "result": s.get("final_result") or s.get("result"),
                "final_result": s.get("final_result") or s.get("result"),
                "created_at": s["created_at"],
            }
            for s in sessions
        ]
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    session = session_service.get_session(session_id)
    return _to_session_response(session)
