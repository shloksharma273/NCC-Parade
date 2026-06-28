from __future__ import annotations

from ..services.camera_service import camera_service
from ..services.session_service import session_service
from ..services.storage_service import storage_service
from ..config import settings


class ReadinessService:
    CRITICAL_KEYS = {"camera_connected", "model_ready", "storage_available"}

    def _check(self, key: str, name: str, status: str, message: str) -> dict:
        return {"key": key, "name": name, "status": status, "message": message}

    def global_readiness(self) -> dict:
        camera_ok = camera_service.check_camera(settings.camera_id)
        from ..ml.drill_analyzer import drill_analyzer

        model_ok = drill_analyzer.model_ready
        storage_ok = storage_service.storage_available()

        checks = [
            self._check(
                "camera_connected",
                "Camera Connected",
                "pass" if camera_ok else "fail",
                "Camera is connected." if camera_ok else "No camera detected. Check connection.",
            ),
            self._check(
                "model_ready",
                "Model Ready",
                "pass" if model_ok else "fail",
                "Analysis model is ready." if model_ok else "Model is not ready yet.",
            ),
            self._check(
                "storage_available",
                "Storage Available",
                "pass" if storage_ok else "fail",
                "Storage is available." if storage_ok else "Storage is not available.",
            ),
            self._check(
                "person_visible",
                "Person Detected",
                "pass" if camera_ok else "warning",
                "Person visible in frame." if camera_ok else "Start camera preview to verify.",
            ),
            self._check(
                "full_body_visible",
                "Full Body Visible",
                "warning",
                "Ensure full body is visible in frame before recording.",
            ),
            self._check(
                "face_visible",
                "Face Visible",
                "warning",
                "Ensure face is clearly visible for salute drills.",
            ),
            self._check(
                "lighting_ok",
                "Lighting Acceptable",
                "pass",
                "Lighting appears acceptable.",
            ),
        ]

        can_record = all(c["status"] != "fail" for c in checks if c["key"] in self.CRITICAL_KEYS)
        return {
            "can_record": can_record,
            "checks": checks,
            "message": "Ready to record." if can_record else "Critical checks failed. Resolve issues before recording.",
        }

    def session_readiness(self, session_id: str) -> dict:
        session = session_service.get_session(session_id)
        usb_index = int(session["camera_id"]) if str(session["camera_id"]).isdigit() else None
        connection = camera_service.check_camera_connection(usb_index=usb_index)
        camera_ok = connection["camera_connected"]

        checks = [
            self._check(
                "camera_connected",
                "Camera Connected",
                "pass" if camera_ok else "fail",
                connection.get("message", "Camera not available."),
            ),
        ]

        return {
            "session_id": session_id,
            "cadet_name": session["cadet_name"],
            "drill_type": session["drill_type"],
            "can_record": camera_ok,
            "checks": checks,
            "message": "Camera ready." if camera_ok else connection.get("message", "Camera not connected."),
        }


readiness_service = ReadinessService()
