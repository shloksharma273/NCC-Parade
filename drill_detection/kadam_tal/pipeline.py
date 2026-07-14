from __future__ import annotations

import json
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HolisticLandmarker,
    HolisticLandmarkerOptions,
    RunningMode,
)

from .config import PipelineConfig
from .landmarks import PeakFrameMetrics, compute_peak_frame_metrics
from .mediapipe_models import ensure_models
from .peak_detection import find_knee_peaks
from .report import generate_pdf_report
from .scoring import FrameScore, score_peak_frame

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def _iter_videos(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [p for p in sorted(input_path.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]


def _peak_to_json(
    rank: int,
    video_name: str,
    item: PeakFrameMetrics,
    frame_score: FrameScore,
    image_rel_path: str,
) -> dict:
    return {
        "rank": rank,
        "video_name": video_name,
        "frame_index": item.frame_index,
        "timestamp_ms": round(item.timestamp_ms, 2),
        "peak_leg": item.peak_leg,
        "peak_knee_lift_px": round(item.peak_knee_lift_px, 2),
        "knee_angle_deg": round(item.peak_knee_angle_deg, 2),
        "foot_angle_deg": round(item.peak_foot_angle_deg, 2),
        "grounded_knee_angle_deg": round(item.grounded_knee_angle_deg, 2),
        "left_elbow_angle_deg": round(item.left_elbow_angle_deg, 2),
        "right_elbow_angle_deg": round(item.right_elbow_angle_deg, 2),
        "left": {
            "knee_angle_deg": round(item.left.knee_angle_deg, 2),
            "foot_angle_deg": round(item.left.foot_angle_deg, 2),
            "knee_lift_px": round(item.left.knee_lift_px, 2),
        },
        "right": {
            "knee_angle_deg": round(item.right.knee_angle_deg, 2),
            "foot_angle_deg": round(item.right.foot_angle_deg, 2),
            "knee_lift_px": round(item.right.knee_lift_px, 2),
        },
        "score": frame_score.to_dict(),
        "output_image_path": image_rel_path,
    }


def _draw_annotations(frame: np.ndarray, metrics: PeakFrameMetrics, frame_score: FrameScore) -> np.ndarray:
    rendered = frame.copy()

    def draw_leg(
        hip: tuple[float, float],
        knee: tuple[float, float],
        ankle: tuple[float, float],
        foot: tuple[float, float],
        color: tuple[int, int, int],
        label: str,
        knee_angle: float,
        foot_angle: float,
    ) -> None:
        hip_i = (int(hip[0]), int(hip[1]))
        knee_i = (int(knee[0]), int(knee[1]))
        ankle_i = (int(ankle[0]), int(ankle[1]))
        foot_i = (int(foot[0]), int(foot[1]))
        cv2.line(rendered, hip_i, knee_i, color, 2)
        cv2.line(rendered, knee_i, ankle_i, color, 2)
        cv2.line(rendered, ankle_i, foot_i, color, 2)
        cv2.circle(rendered, knee_i, 6, color, -1)
        cv2.circle(rendered, ankle_i, 6, color, -1)
        cv2.putText(
            rendered,
            f"{label} knee {knee_angle:.0f}",
            (knee_i[0] + 8, knee_i[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )

    def draw_arm(
        shoulder: tuple[float, float],
        elbow: tuple[float, float],
        wrist: tuple[float, float],
        color: tuple[int, int, int],
    ) -> None:
        shoulder_i = (int(shoulder[0]), int(shoulder[1]))
        elbow_i = (int(elbow[0]), int(elbow[1]))
        wrist_i = (int(wrist[0]), int(wrist[1]))
        cv2.line(rendered, shoulder_i, elbow_i, color, 2)
        cv2.line(rendered, elbow_i, wrist_i, color, 2)
        cv2.circle(rendered, elbow_i, 5, color, -1)

    draw_leg(
        metrics.left_hip_px,
        metrics.left_knee_px,
        metrics.left_ankle_px,
        metrics.left_foot_px,
        (255, 180, 0),
        "L",
        metrics.left.knee_angle_deg,
        metrics.left.foot_angle_deg,
    )
    draw_leg(
        metrics.right_hip_px,
        metrics.right_knee_px,
        metrics.right_ankle_px,
        metrics.right_foot_px,
        (0, 180, 255),
        "R",
        metrics.right.knee_angle_deg,
        metrics.right.foot_angle_deg,
    )
    draw_arm(metrics.left_shoulder_px, metrics.left_elbow_px, metrics.left_wrist_px, (200, 200, 0))
    draw_arm(metrics.right_shoulder_px, metrics.right_elbow_px, metrics.right_wrist_px, (200, 200, 0))

    label = (
        f"score {frame_score.total:.1f}/10 | peak {metrics.peak_leg} | "
        f"knee {metrics.peak_knee_angle_deg:.0f} | foot {metrics.peak_foot_angle_deg:.0f}"
    )
    cv2.putText(
        rendered,
        label,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )
    return rendered


def _load_frame(video_path: Path, frame_index: int) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def process_video(video_path: Path, config: PipelineConfig) -> dict:
    output_root = config.output_dir / video_path.stem
    output_root.mkdir(parents=True, exist_ok=True)
    annotated_dir = output_root / "peak_frames"
    raw_dir = output_root / "raw_frames"
    if config.save_annotated_frames:
        annotated_dir.mkdir(parents=True, exist_ok=True)
    if config.save_raw_frames:
        raw_dir.mkdir(parents=True, exist_ok=True)

    model_path = ensure_models()
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    holistic_options = HolisticLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=RunningMode.VIDEO,
        min_pose_detection_confidence=config.min_detection_confidence,
        min_pose_landmarks_confidence=config.min_detection_confidence,
    )
    holistic = HolisticLandmarker.create_from_options(holistic_options)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_index = 0
    processed_frames = 0
    valid_frames = 0
    metrics: list[PeakFrameMetrics] = []

    try:
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            if frame_index % config.every_k_frames != 0:
                frame_index += 1
                continue

            height, width = frame_bgr.shape[:2]
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            timestamp_ms = (frame_index / fps) * 1000.0

            result = holistic.detect_for_video(mp_image, int(timestamp_ms))
            processed_frames += 1

            frame_metrics = compute_peak_frame_metrics(
                result.pose_landmarks,
                frame_index=frame_index,
                timestamp_ms=timestamp_ms,
                width=width,
                height=height,
            )
            if frame_metrics is not None:
                metrics.append(frame_metrics)
                valid_frames += 1

            frame_index += 1
    finally:
        cap.release()
        holistic.close()

    peaks = find_knee_peaks(
        metrics,
        smooth_window=config.smooth_window,
        min_distance=config.min_peak_distance_frames,
        min_prominence_px=config.min_peak_prominence_px,
        min_prominence_ratio=config.min_peak_prominence_ratio,
    )

    peak_frames: list[dict] = []
    frame_scores: list[float] = []

    for rank, item in enumerate(peaks, start=1):
        frame_score = score_peak_frame(
            peak_knee_angle_deg=item.peak_knee_angle_deg,
            peak_foot_angle_deg=item.peak_foot_angle_deg,
            grounded_knee_angle_deg=item.grounded_knee_angle_deg,
            left_elbow_angle_deg=item.left_elbow_angle_deg,
            right_elbow_angle_deg=item.right_elbow_angle_deg,
            difficulty=config.difficulty,
        )
        frame_scores.append(frame_score.total)

        image_rel_path = ""
        frame_bgr = _load_frame(video_path, item.frame_index)
        if frame_bgr is not None:
            file_base = f"peak_{rank:02d}_frame_{item.frame_index:06d}_{item.peak_leg}"
            if config.save_annotated_frames:
                annotated = _draw_annotations(frame_bgr, item, frame_score)
                annotated_path = annotated_dir / f"{file_base}.jpg"
                cv2.imwrite(str(annotated_path), annotated)
                image_rel_path = str(annotated_path.relative_to(config.output_dir))
            if config.save_raw_frames:
                raw_path = raw_dir / f"{file_base}.jpg"
                cv2.imwrite(str(raw_path), frame_bgr)

        peak_frames.append(_peak_to_json(rank, video_path.name, item, frame_score, image_rel_path))

    kadam_tal_count = len(peak_frames)
    total_score = round(sum(frame_scores), 2)
    average_score = round(total_score / kadam_tal_count, 2) if kadam_tal_count else 0.0

    result_payload = {
        "video_name": video_path.name,
        "difficulty": config.difficulty,
        "report_metadata": config.report_metadata.to_dict() if config.report_metadata else None,
        "summary": {
            "kadam_tal_count": kadam_tal_count,
            "total_score": total_score,
            "max_possible_score": kadam_tal_count * 10,
            "average_score_per_kadam_tal": average_score,
        },
        "peak_frames": peak_frames,
    }

    result_json_path = output_root / "results.json"
    with result_json_path.open("w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2)

    report_pdf_path = output_root / "kadam_tal_report.pdf"
    generate_pdf_report(
        results_path=result_json_path,
        output_path=report_pdf_path,
        output_dir=config.output_dir,
        metadata=config.report_metadata,
    )

    return {
        "video": str(video_path),
        "processed_frames": processed_frames,
        "valid_scored_frames": valid_frames,
        "peak_count": kadam_tal_count,
        "kadam_tal_count": kadam_tal_count,
        "total_score": total_score,
        "average_score": average_score,
        "difficulty": config.difficulty,
        "results_json": str(result_json_path),
        "report_pdf": str(report_pdf_path),
    }


def run_pipeline(config: PipelineConfig) -> list[dict]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    videos = _iter_videos(config.input_path)
    if not videos:
        raise RuntimeError(f"No supported videos found at: {config.input_path}")

    return [process_video(video, config) for video in videos]
