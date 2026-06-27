from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..config import FRAMES_MEDIA_DIR, REPORTS_DIR, RAW_MEDIA_DIR
from ..models.api_models import DrillReport, ReportMedia, ReportParameter
from ..utils.file_utils import media_url
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

        report = DrillReport(
            session_id=session_id,
            cadet_id=session.get("cadet_id"),
            cadet_name=session["cadet_name"],
            drill_type=session["drill_type"],
            attempt_number=session["attempt_number"],
            score=int(analysis["score"]),
            result=analysis["result"],
            summary=analysis["summary"],
            parameters=[ReportParameter(**p) for p in analysis["parameters"]],
            media=ReportMedia(
                raw_video_url=raw_video_url,
                annotated_video_url=analysis.get("annotated_video_path"),
                key_frame_url=key_frame_url,
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


report_service = ReportService()
