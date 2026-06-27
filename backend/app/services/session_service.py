from __future__ import annotations

from fastapi import HTTPException, status

from ..config import SUPPORTED_DRILL_TYPES
from ..db.repositories import ProgressRepository, SessionRepository
from ..models.api_models import CreateSessionRequest
from ..models.session_models import SessionStatus, can_transition
from ..services.camera_service import camera_service
from ..services.storage_service import storage_service
from ..utils.id_generator import generate_session_id
from ..utils.time_utils import utc_now_iso


class SessionService:
    def __init__(self) -> None:
        self.sessions = SessionRepository()
        self.progress = ProgressRepository()

    def create_session(self, request: CreateSessionRequest) -> dict:
        if request.drill_type not in SUPPORTED_DRILL_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "UNSUPPORTED_DRILL_TYPE",
                    "message": f"Drill type '{request.drill_type}' is not supported.",
                },
            )

        session_id = generate_session_id(self.sessions)
        attempt_number = self.sessions.next_attempt_number(request.cadet_id, request.drill_type)
        camera_id = request.camera_id or "0"
        camera_ok = camera_service.check_camera(int(camera_id))

        initial_status = SessionStatus.READY if camera_ok else SessionStatus.CREATED
        session = self.sessions.create_session(
            {
                "session_id": session_id,
                "cadet_id": request.cadet_id,
                "cadet_name": request.cadet_name,
                "drill_type": request.drill_type,
                "attempt_number": attempt_number,
                "camera_id": camera_id,
                "status": initial_status.value,
                "created_at": utc_now_iso(),
            }
        )
        return session

    def get_session(self, session_id: str) -> dict:
        session = self.sessions.get_session(session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "SESSION_NOT_FOUND", "message": "Session not found."},
            )
        return session

    def list_sessions(
        self,
        limit: int = 20,
        drill_type: str | None = None,
        cadet_id: str | None = None,
    ) -> list[dict]:
        return self.sessions.list_sessions(limit=limit, drill_type=drill_type, cadet_id=cadet_id)

    def transition(self, session_id: str, target: SessionStatus, **fields) -> dict:
        session = self.get_session(session_id)
        current = SessionStatus(session["status"])
        if not can_transition(current, target):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "INVALID_SESSION_STATE",
                    "message": f"Cannot transition from {current.value} to {target.value}.",
                },
            )
        return self.sessions.update_session(session_id, status=target.value, **fields)

    def mark_failed(self, session_id: str, message: str) -> dict:
        return self.sessions.update_session(
            session_id,
            status=SessionStatus.FAILED.value,
            error_message=message,
            completed_at=utc_now_iso(),
        )

    def system_status(self) -> dict:
        from ..config import settings
        from ..ml.drill_analyzer import drill_analyzer

        camera_ok = camera_service.check_camera()
        active = camera_service.active_session_id
        return {
            "backend_status": "ready",
            "camera_connected": camera_ok,
            "camera_id": str(settings.camera_id),
            "model_ready": drill_analyzer.model_ready,
            "active_session_id": active,
            "storage_available": storage_service.storage_available(),
        }


session_service = SessionService()
