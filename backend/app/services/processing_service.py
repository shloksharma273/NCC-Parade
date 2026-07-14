from __future__ import annotations

import asyncio

from ..db.repositories import ProgressRepository, SessionRepository
from ..models.session_models import ProcessingStage, SessionStatus
from ..services.report_service import report_service
from ..services.session_service import session_service
from ..services.websocket_manager import ws_manager
from ..utils.time_utils import utc_now_iso


class ProcessingService:
    def __init__(self) -> None:
        self.sessions = SessionRepository()
        self.progress = ProgressRepository()

    async def run_analysis(self, session_id: str, video_path: str) -> None:
        session = session_service.get_session(session_id)
        loop = asyncio.get_running_loop()

        def progress_callback(stage: ProcessingStage, progress: int, message: str) -> None:
            self._record_progress(session_id, SessionStatus.PROCESSING.value, stage.value, progress, message)
            payload = {
                "type": "processing_update",
                "session_id": session_id,
                "status": SessionStatus.PROCESSING.value,
                "stage": stage.value,
                "progress": progress,
                "message": message,
                "timestamp": utc_now_iso(),
            }
            loop.call_soon_threadsafe(lambda: asyncio.create_task(ws_manager.broadcast(session_id, payload)))

        try:
            from ..ml.drill_analyzer import drill_analyzer

            # camera_view chosen at session creation (e.g. baju_swing front/side) drives the
            # analyzer's view mode; normalise case and default to "side". Drills that ignore
            # view (salute/kadam_tal) are unaffected.
            view = (session.get("camera_view") or "side").strip().lower()
            analysis = await asyncio.to_thread(
                drill_analyzer.analyze,
                video_path,
                session["drill_type"],
                session_id,
                progress_callback,
                view,
            )
            report = report_service.build_report(session, analysis, session_id)
            report_path = report_service.save_report(session_id, report)

            self.sessions.update_session(
                session_id,
                status=SessionStatus.REPORT_READY.value,
                report_path=str(report_path),
                score=analysis["score"],
                result=analysis["result"],
                ai_result=analysis["result"],
                final_result=analysis["result"],
                completed_at=utc_now_iso(),
                error_message=None,
            )
            self._record_progress(
                session_id,
                SessionStatus.REPORT_READY.value,
                ProcessingStage.COMPLETED.value,
                100,
                "Report is ready.",
            )
            await ws_manager.broadcast(
                session_id,
                {
                    "type": "report_ready",
                    "session_id": session_id,
                    "status": SessionStatus.REPORT_READY.value,
                    "report_url": f"/sessions/{session_id}/report",
                    "timestamp": utc_now_iso(),
                },
            )
        except Exception as exc:
            message = str(exc) or "Analysis failed because required body landmarks were not detected."
            session_service.mark_failed(session_id, message)
            self._record_progress(
                session_id,
                SessionStatus.FAILED.value,
                ProcessingStage.FAILED.value,
                0,
                message,
            )
            await ws_manager.broadcast(
                session_id,
                {
                    "type": "status_update",
                    "session_id": session_id,
                    "status": SessionStatus.FAILED.value,
                    "message": message,
                    "timestamp": utc_now_iso(),
                },
            )

    def _record_progress(
        self,
        session_id: str,
        status_value: str,
        stage: str,
        progress: int,
        message: str,
    ) -> None:
        self.progress.add_event(
            session_id=session_id,
            status=status_value,
            stage=stage,
            progress=progress,
            message=message,
            created_at=utc_now_iso(),
        )

    def get_progress(self, session_id: str) -> dict:
        session = session_service.get_session(session_id)
        latest = self.progress.get_latest(session_id)
        if latest:
            return {
                "session_id": session_id,
                "status": latest["status"],
                "stage": latest["stage"],
                "progress": latest["progress"],
                "message": latest["message"],
            }
        return {
            "session_id": session_id,
            "status": session["status"],
            "stage": ProcessingStage.VIDEO_SAVED.value,
            "progress": 0,
            "message": "Waiting for processing to start.",
        }


processing_service = ProcessingService()
