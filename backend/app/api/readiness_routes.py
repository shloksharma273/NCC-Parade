from __future__ import annotations

from fastapi import APIRouter

from ..services.readiness_service import readiness_service

router = APIRouter(tags=["readiness"])


@router.get("/readiness")
def global_readiness() -> dict:
    return readiness_service.global_readiness()


@router.get("/sessions/{session_id}/readiness")
def session_readiness(session_id: str) -> dict:
    return readiness_service.session_readiness(session_id)
