from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from ..config import PROJECT_ROOT, SUPPORTED_DRILL_TYPES, settings
from ..models.session_models import ProcessingStage

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from knee_peak_detector.config import PipelineConfig
from knee_peak_detector.pipeline import process_video


ProgressCallback = Callable[[ProcessingStage, int, str], None]


class DrillAnalyzer:
    def __init__(self) -> None:
        self._model_checked = False

    def ensure_model_ready(self) -> bool:
        try:
            from knee_peak_detector.mediapipe_models import ensure_models

            ensure_models()
            self._model_checked = True
            return True
        except Exception:
            return False

    @property
    def model_ready(self) -> bool:
        if self._model_checked:
            return True
        return self.ensure_model_ready()

    def analyze(
        self,
        video_path: str,
        drill_type: str,
        session_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> dict:
        if drill_type not in SUPPORTED_DRILL_TYPES:
            raise ValueError(f"Unsupported drill type: {drill_type}")

        if drill_type == "salute":
            raise NotImplementedError("Salute drill analysis is not implemented yet. Use kadam_tal.")

        def emit(stage: ProcessingStage, progress: int, message: str) -> None:
            if progress_callback:
                progress_callback(stage, progress, message)

        emit(ProcessingStage.VIDEO_SAVED, 10, "Video saved successfully.")
        emit(ProcessingStage.POSE_EXTRACTION, 25, "Extracting pose landmarks.")

        output_dir = settings.ml_output_dir / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        config = PipelineConfig(
            input_path=Path(video_path),
            output_dir=output_dir,
            difficulty=settings.ml_difficulty,
            save_annotated_frames=True,
        )

        emit(ProcessingStage.POSE_EXTRACTION, 40, "Running pose detection on video frames.")
        summary = process_video(Path(video_path), config)

        emit(ProcessingStage.PARAMETER_CALCULATION, 65, "Calculating knee angle, foot angle, and posture scores.")
        emit(ProcessingStage.GROUND_TRUTH_COMPARISON, 80, "Comparing parameters against ideal drill form.")
        emit(ProcessingStage.REPORT_GENERATION, 95, "Generating drill report.")

        import json

        results_path = Path(summary["results_json"])
        with results_path.open(encoding="utf-8") as f:
            ml_results = json.load(f)

        peak_frames = ml_results.get("peak_frames", [])
        avg_score = ml_results.get("summary", {}).get("average_score_per_kadam_tal", 0.0)
        kadam_tal_count = ml_results.get("summary", {}).get("kadam_tal_count", 0)

        key_frame_path = None
        if peak_frames:
            rel = peak_frames[0].get("output_image_path", "")
            if rel:
                candidate = output_dir / rel
                if not candidate.exists():
                    candidate = output_dir / Path(rel).name
                if candidate.exists():
                    key_frame_path = str(candidate)

        emit(ProcessingStage.COMPLETED, 100, "Analysis completed.")

        return {
            "score": int(round(avg_score * 10)),
            "average_score_per_kadam_tal": avg_score,
            "kadam_tal_count": kadam_tal_count,
            "result": self._result_label(avg_score * 10),
            "summary": self._build_summary(peak_frames, avg_score, kadam_tal_count),
            "parameters": self._build_parameters(peak_frames),
            "annotated_video_path": None,
            "key_frame_path": key_frame_path,
            "ml_results_path": str(results_path),
            "report_pdf_path": summary.get("report_pdf"),
            "peak_frames": peak_frames,
            "ml_summary": ml_results.get("summary", {}),
        }

    @staticmethod
    def _result_label(score_0_100: float) -> str:
        if score_0_100 >= 70:
            return "pass"
        if score_0_100 >= 50:
            return "needs_correction"
        return "fail"

    @staticmethod
    def _build_summary(peak_frames: list[dict], avg_score: float, kadam_tal_count: int) -> list[str]:
        if kadam_tal_count == 0:
            return ["No kadam tal repetitions were detected in the recording."]

        summaries = [f"Detected {kadam_tal_count} kadam tal with average score {avg_score:.2f}/10."]
        if peak_frames:
            best = max(peak_frames, key=lambda f: f["score"]["total"])
            worst = min(peak_frames, key=lambda f: f["score"]["total"])
            summaries.append(
                f"Best repetition: kadam tal #{best['rank']} scored {best['score']['total']:.2f}/10."
            )
            summaries.append(
                f"Weakest repetition: kadam tal #{worst['rank']} scored {worst['score']['total']:.2f}/10."
            )

            avg_params = {
                "peak_knee_angle": 0.0,
                "peak_foot_angle": 0.0,
                "grounded_leg": 0.0,
                "hands": 0.0,
            }
            for frame in peak_frames:
                for key in avg_params:
                    avg_params[key] += frame["score"][key]
            for key in avg_params:
                avg_params[key] /= len(peak_frames)

            if avg_params["peak_knee_angle"] < 7:
                summaries.append("Peak knee angle was frequently below the ideal 90 degrees.")
            if avg_params["peak_foot_angle"] < 7:
                summaries.append("Foot angle during peak position needs improvement.")
            if avg_params["grounded_leg"] < 7:
                summaries.append("Grounded leg was not consistently straight.")
            if avg_params["hands"] < 7:
                summaries.append("Arm posture was not consistently straight.")
        return summaries

    @staticmethod
    def _build_parameters(peak_frames: list[dict]) -> list[dict]:
        if not peak_frames:
            return []

        keys = [
            ("Peak Knee Angle", "peak_knee_angle", "90°", "Keep peak leg knee angle close to 90 degrees."),
            ("Peak Foot Angle", "peak_foot_angle", "90°", "Maintain 90 degree angle between shin and foot."),
            ("Grounded Leg", "grounded_leg", "180° (straight)", "Keep the grounded leg straight."),
            ("Hands", "hands", "180° (straight arms)", "Keep both arms straight throughout the drill."),
        ]

        parameters = []
        for name, key, expected, feedback in keys:
            values = [frame["score"][key] for frame in peak_frames]
            avg = sum(values) / len(values)
            status = "pass" if avg >= 7 else "needs_correction" if avg >= 5 else "fail"
            parameters.append(
                {
                    "name": name,
                    "expected": expected,
                    "actual": f"{avg:.2f}/10 average",
                    "score": round(avg / 10, 2),
                    "status": status,
                    "feedback": feedback if avg < 7 else "Good form on this parameter.",
                }
            )
        return parameters


drill_analyzer = DrillAnalyzer()
