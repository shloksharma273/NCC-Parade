from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..models.api_models import HealthResponse, SystemStatusResponse
from ..services.session_service import session_service

router = APIRouter(tags=["status"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(version=settings.version)


@router.get("/status", response_model=SystemStatusResponse)
def system_status() -> SystemStatusResponse:
    return SystemStatusResponse(**session_service.system_status())
