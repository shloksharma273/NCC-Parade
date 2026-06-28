from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..config import FRAMES_MEDIA_DIR, REPORTS_DIR, REPORTS_MEDIA_DIR, settings
from ..models.api_models import DrillReport, ReportMedia, ReportParameter
from ..utils.file_utils import media_url, unique_report_pdf_path
from ..utils.time_utils import utc_now_iso


class ReportService:
    def build_report(
        self,
        session: dict,
        analysis: dict,
        session_id: str,
    ) -> dict:
        key_frame_url = None
        key_frame_src = analysis.get("key_frame_path")
        if key_frame_src and Path(key_frame_src).exists():
            dest = FRAMES_MEDIA_DIR / f"{session_id}_key.jpg"
            shutil.copy2(key_frame_src, dest)
            key_frame_url = media_url(f"frames/{dest.name}")

        for idx, frame in enumerate(analysis.get("peak_frames", []), start=1):
            rel = frame.get("output_image_path", "")
            if not rel:
                continue
            src = Path(analysis["ml_results_path"]).parent.parent / rel
            if not src.exists():
                src = Path(analysis["ml_results_path"]).parent / Path(rel).name
            if src.exists():
                dest = FRAMES_MEDIA_DIR / f"{session_id}_peak_{idx:02d}.jpg"
                shutil.copy2(src, dest)

        raw_video_url = None
        if session.get("video_path") and Path(session["video_path"]).exists():
            raw_video_url = media_url(f"raw/{Path(session['video_path']).name}")

        report_pdf_url = None
        report_pdf_filename = None
        pdf_src = analysis.get("report_pdf_path")
        if pdf_src and Path(pdf_src).exists():
            recorded_at = session.get("stopped_at") or session.get("started_at") or session.get("created_at")
            dest = unique_report_pdf_path(
                REPORTS_MEDIA_DIR,
                session["cadet_name"],
                recorded_at,
            )
            shutil.copy2(pdf_src, dest)
            report_pdf_filename = dest.name
            report_pdf_url = media_url(f"reports/{dest.name}")

        report = DrillReport(
            session_id=session_id,
            cadet_id=session.get("cadet_id"),
            cadet_name=session["cadet_name"],
            squad=session.get("squad"),
            unit=session.get("unit"),
            drill_type=session["drill_type"],
            attempt_number=session["attempt_number"],
            score=int(analysis["score"]),
            result=session.get("final_result") or analysis["result"],
            ai_result=session.get("ai_result") or analysis["result"],
            instructor_decision=session.get("instructor_decision"),
            instructor_remarks=session.get("instructor_remarks"),
            final_result=session.get("final_result") or analysis["result"],
            summary=analysis["summary"],
            parameters=[ReportParameter(**p) for p in analysis["parameters"]],
            media=ReportMedia(
                raw_video_url=raw_video_url,
                annotated_video_url=analysis.get("annotated_video_path"),
                key_frame_url=key_frame_url,
                report_pdf_url=report_pdf_url,
                report_pdf_filename=report_pdf_filename,
            ),
            created_at=utc_now_iso(),
            kadam_tal_count=analysis.get("kadam_tal_count"),
            average_score_per_kadam_tal=analysis.get("average_score_per_kadam_tal"),
            peak_frames=analysis.get("peak_frames", []),
        )
        return report.model_dump()

    def save_report(self, session_id: str, report: dict) -> Path:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / f"{session_id}.json"
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return report_path

    def load_report(self, report_path: str) -> dict | None:
        path = Path(report_path)
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    def resolve_pdf_path(self, session_id: str, report: dict | None = None) -> Path | None:
        if report:
            media = report.get("media") or {}
            pdf_filename = media.get("report_pdf_filename")
            if pdf_filename:
                candidate = REPORTS_MEDIA_DIR / pdf_filename
                if candidate.exists():
                    return candidate

            pdf_url = media.get("report_pdf_url")
            if pdf_url:
                candidate = REPORTS_MEDIA_DIR / Path(pdf_url).name
                if candidate.exists():
                    return candidate

        legacy_path = REPORTS_MEDIA_DIR / f"{session_id}.pdf"
        if legacy_path.exists():
            return legacy_path

        ml_dir = settings.ml_output_dir / session_id
        if ml_dir.exists() and report:
            for pattern in ("kadam_tal_report.pdf", "salute_report.pdf"):
                for pdf_path in ml_dir.rglob(pattern):
                    if pdf_path.is_file():
                        recorded_at = report.get("created_at")
                        dest = unique_report_pdf_path(
                            REPORTS_MEDIA_DIR,
                            report.get("cadet_name", "Cadet"),
                            recorded_at,
                        )
                        shutil.copy2(pdf_path, dest)
                        return dest
        return None

    def report_pdf_filename(self, session: dict, report: dict | None = None) -> str:
        if report:
            filename = (report.get("media") or {}).get("report_pdf_filename")
            if filename:
                return filename

        recorded_at = session.get("stopped_at") or session.get("started_at") or session.get("created_at")
        from ..utils.file_utils import build_report_pdf_filename

        return build_report_pdf_filename(session.get("cadet_name", "Cadet"), recorded_at)


report_service = ReportService()
