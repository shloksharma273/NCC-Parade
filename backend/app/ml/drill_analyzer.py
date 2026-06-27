from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

from ..config import PROJECT_ROOT, SUPPORTED_DRILL_TYPES, settings
from ..models.session_models import ProcessingStage

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ProgressCallback = Callable[[ProcessingStage, int, str], None]


class DrillAnalyzer:
    def __init__(self) -> None:
        self._model_checked = False

    def ensure_model_ready(self) -> bool:
        try:
            from salute_detector.mediapipe_models import ensure_models

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
            return self._analyze_salute(video_path, session_id, progress_callback)
        if drill_type == "kadam_tal":
            return self._analyze_kadam_tal(video_path, session_id, progress_callback)
        raise ValueError(f"Drill type '{drill_type}' is not implemented yet.")

    def _analyze_kadam_tal(
        self,
        video_path: str,
        session_id: str,
        progress_callback: ProgressCallback | None,
    ) -> dict:
        from knee_peak_detector.config import PipelineConfig
        from knee_peak_detector.pipeline import process_video

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

        results_path = Path(summary["results_json"])
        with results_path.open(encoding="utf-8") as f:
            ml_results = json.load(f)

        peak_frames = ml_results.get("peak_frames", [])
        avg_score = ml_results.get("summary", {}).get("average_score_per_kadam_tal", 0.0)
        kadam_tal_count = ml_results.get("summary", {}).get("kadam_tal_count", 0)
        key_frame_path = self._resolve_key_frame(output_dir, peak_frames)

        emit(ProcessingStage.COMPLETED, 100, "Analysis completed.")

        return {
            "score": int(round(avg_score * 10)),
            "average_score_per_kadam_tal": avg_score,
            "kadam_tal_count": kadam_tal_count,
            "result": self._result_label(avg_score * 10),
            "summary": self._build_kadam_tal_summary(peak_frames, avg_score, kadam_tal_count),
            "parameters": self._build_kadam_tal_parameters(peak_frames),
            "annotated_video_path": None,
            "key_frame_path": key_frame_path,
            "ml_results_path": str(results_path),
            "report_pdf_path": summary.get("report_pdf"),
            "peak_frames": peak_frames,
            "ml_summary": ml_results.get("summary", {}),
        }

    def _analyze_salute(
        self,
        video_path: str,
        session_id: str,
        progress_callback: ProgressCallback | None,
    ) -> dict:
        from salute_detector.config import PipelineConfig as SaluteConfig
        from salute_detector.pipeline import process_video as process_salute_video

        def emit(stage: ProcessingStage, progress: int, message: str) -> None:
            if progress_callback:
                progress_callback(stage, progress, message)

        emit(ProcessingStage.VIDEO_SAVED, 10, "Video saved successfully.")
        emit(ProcessingStage.POSE_EXTRACTION, 25, "Extracting face and hand landmarks.")

        output_dir = settings.ml_output_dir / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        config = SaluteConfig(
            input_path=Path(video_path),
            output_dir=output_dir,
            difficulty=settings.ml_difficulty,
            save_annotated_frames=True,
            enable_posture_analysis=True,
            force_posture_analysis=True,
        )

        emit(ProcessingStage.POSE_EXTRACTION, 40, "Finding salute candidate frames.")
        summary = process_salute_video(Path(video_path), config)

        emit(ProcessingStage.PARAMETER_CALCULATION, 65, "Calculating elbow angle and hand-eyebrow distance.")
        emit(ProcessingStage.GROUND_TRUTH_COMPARISON, 80, "Scoring salute posture parameters.")
        emit(ProcessingStage.REPORT_GENERATION, 95, "Generating salute report.")

        results_path = Path(summary["results_json"])
        with results_path.open(encoding="utf-8") as f:
            candidate_frames = json.load(f)

        posture_analyses: list[dict] = []
        posture_json = summary.get("posture_analysis_json")
        if posture_json and Path(posture_json).exists():
            with Path(posture_json).open(encoding="utf-8") as f:
                posture_analyses = json.load(f)

        if posture_analyses:
            avg_weighted = sum(item["weighted_score"] for item in posture_analyses) / len(posture_analyses)
            best = max(posture_analyses, key=lambda item: item["weighted_score"])
            key_frame_path = self._resolve_output_image(output_dir, best.get("output_image_path", ""))
        elif candidate_frames:
            avg_weighted = 0.0
            key_frame_path = self._resolve_output_image(
                output_dir, candidate_frames[0].get("output_image_path", "")
            )
        else:
            raise RuntimeError("Analysis failed because required body landmarks were not detected.")

        score_0_100 = avg_weighted * 10 if posture_analyses else 0

        emit(ProcessingStage.COMPLETED, 100, "Analysis completed.")

        return {
            "score": int(round(score_0_100)),
            "salute_candidate_count": len(candidate_frames),
            "result": self._result_label(score_0_100),
            "summary": self._build_salute_summary(candidate_frames, posture_analyses, score_0_100),
            "parameters": self._build_salute_parameters(posture_analyses),
            "annotated_video_path": None,
            "key_frame_path": key_frame_path,
            "ml_results_path": str(results_path),
            "posture_analysis_path": posture_json,
            "candidate_frames": candidate_frames,
            "posture_analyses": posture_analyses,
        }

    @staticmethod
    def _resolve_output_image(output_dir: Path, rel_path: str) -> str | None:
        if not rel_path:
            return None
        candidate = output_dir / rel_path
        if candidate.exists():
            return str(candidate)
        fallback = output_dir / Path(rel_path).name
        return str(fallback) if fallback.exists() else None

    @staticmethod
    def _resolve_key_frame(output_dir: Path, peak_frames: list[dict]) -> str | None:
        if not peak_frames:
            return None
        rel = peak_frames[0].get("output_image_path", "")
        return DrillAnalyzer._resolve_output_image(output_dir, rel)

    @staticmethod
    def _result_label(score_0_100: float) -> str:
        if score_0_100 >= 70:
            return "pass"
        if score_0_100 >= 50:
            return "needs_correction"
        return "fail"

    @staticmethod
    def _build_kadam_tal_summary(peak_frames: list[dict], avg_score: float, kadam_tal_count: int) -> list[str]:
        if kadam_tal_count == 0:
            return ["No kadam tal repetitions were detected in the recording."]

        summaries = [f"Detected {kadam_tal_count} kadam tal with average score {avg_score:.2f}/10."]
        if peak_frames:
            best = max(peak_frames, key=lambda f: f["score"]["total"])
            worst = min(peak_frames, key=lambda f: f["score"]["total"])
            summaries.append(f"Best repetition: kadam tal #{best['rank']} scored {best['score']['total']:.2f}/10.")
            summaries.append(f"Weakest repetition: kadam tal #{worst['rank']} scored {worst['score']['total']:.2f}/10.")
        return summaries

    @staticmethod
    def _build_kadam_tal_parameters(peak_frames: list[dict]) -> list[dict]:
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

    @staticmethod
    def _build_salute_summary(
        candidate_frames: list[dict],
        posture_analyses: list[dict],
        score_0_100: float,
    ) -> list[str]:
        summaries = [f"Detected {len(candidate_frames)} salute candidate frame(s)."]
        if posture_analyses:
            summaries.append(f"Average posture score: {score_0_100:.0f}/100.")
            best = max(posture_analyses, key=lambda item: item["weighted_score"])
            summaries.append(
                f"Best salute frame #{best['rank']} scored {best['weighted_score']:.2f}/10."
            )

            avg_elbow = sum(item["elbow_angle_deg"] for item in posture_analyses) / len(posture_analyses)
            avg_heels = sum(item["heels_score"] for item in posture_analyses) / len(posture_analyses)
            if avg_elbow < 40:
                summaries.append("Elbow angle was lower than the expected 45 degrees.")
            if avg_heels < 7:
                summaries.append("Feet together and foot angle need improvement.")
        else:
            summaries.append("Posture scoring was not available; only salute proximity frames were detected.")
        return summaries

    @staticmethod
    def _build_salute_parameters(posture_analyses: list[dict]) -> list[dict]:
        if not posture_analyses:
            return []

        specs = [
            (
                "Fingers Joined",
                "fingers_joined_score",
                "joined",
                lambda items: f"{sum(i['fingers_joined_score'] for i in items) / len(items):.2f}/10 average",
                "Keep right hand fingers and thumb joined.",
            ),
            (
                "Right Elbow Angle",
                "elbow_angle_score",
                "45°",
                lambda items: f"{sum(i['elbow_angle_deg'] for i in items) / len(items):.1f}° average",
                "Raise the elbow slightly toward 45 degrees.",
            ),
            (
                "Heels Together",
                "heels_score",
                "feet together, ~30°",
                lambda items: f"{sum(i['heel_angle_deg'] for i in items) / len(items):.1f}° average",
                "Keep heels together with correct foot angle.",
            ),
            (
                "Left Hand Attached",
                "left_hand_attached_score",
                "attached to body",
                lambda items: f"{sum(i['left_hand_attached_score'] for i in items) / len(items):.2f}/10 average",
                "Keep left hand attached to the body.",
            ),
        ]

        parameters = []
        for name, score_key, expected, actual_fn, feedback in specs:
            avg_score = sum(item[score_key] for item in posture_analyses) / len(posture_analyses)
            status = "pass" if avg_score >= 7 else "needs_correction" if avg_score >= 5 else "fail"
            parameters.append(
                {
                    "name": name,
                    "expected": expected,
                    "actual": actual_fn(posture_analyses),
                    "score": round(avg_score / 10, 2),
                    "status": status,
                    "feedback": feedback if avg_score < 7 else "Good form on this parameter.",
                }
            )
        return parameters


drill_analyzer = DrillAnalyzer()
