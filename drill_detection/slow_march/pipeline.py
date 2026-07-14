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
from .key_frame_detection import find_step_peaks
from .landmarks import SlowMarchFrameMetrics, assign_leg_roles_by_position, compute_frame_metrics
from .mediapipe_models import ensure_models
from .report import generate_pdf_report
from .scoring import FrameScore, score_frame

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def _iter_videos(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [p for p in sorted(input_path.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]


def _score_frame_from_metrics(item: SlowMarchFrameMetrics, config: PipelineConfig) -> FrameScore:
    return score_frame(
        left_elbow_angle_deg=item.left_elbow_angle_deg,
        right_elbow_angle_deg=item.right_elbow_angle_deg,
        head_yaw_ratio=item.head_yaw_ratio,
        head_tilt_deg=item.head_tilt_deg,
        grounded_knee_angle_deg=item.grounded_knee_angle_deg,
        grounded_vertical_deg=item.grounded_vertical_deg,
        raised_foot_horizontal_deg=item.raised_foot_horizontal_deg,
        difficulty=config.difficulty,
        view=config.view,
        target_arm_angle_deg=config.target_arm_angle_deg,
        target_grounded_knee_deg=config.target_grounded_knee_deg,
        target_grounded_vertical_deg=config.target_grounded_vertical_deg,
        target_foot_horizontal_deg=config.target_foot_horizontal_deg,
        raised_foot_is_mandatory=config.raised_foot_is_mandatory,
        raised_foot_pass_threshold=config.raised_foot_pass_threshold,
        raised_foot_gate_cap=config.raised_foot_gate_cap,
    )


def _key_frame_to_json(
    rank: int,
    video_name: str,
    item: SlowMarchFrameMetrics,
    frame_score: FrameScore,
    image_rel_path: str,
) -> dict:
    return {
        "rank": rank,
        "video_name": video_name,
        "frame_index": item.frame_index,
        "timestamp_ms": round(item.timestamp_ms, 2),
        "inter_leg_angle_deg": round(item.inter_leg_angle_deg, 2),
        "stride_separation_norm": item.stride_separation_norm,  # front leg farthest (higher == wider stride)
        "hind_foot_speed_norm": item.hind_foot_speed_norm,      # hind leg static (0 == planted)
        "hind_foot_flat_deg": item.hind_foot_flat_deg,          # foot_passing: hind sole flatness (0 == grounded flat)
        "front_foot_flat_deg": item.front_foot_flat_deg,        # foot_passing: front sole flatness (0 == parallel)
        "inter_leg_split_deg": item.inter_leg_split_deg,        # foot_passing: leg split (small == feet together)
        "grounded_leg": item.grounded_leg,
        "raised_leg": item.raised_leg,
        "grounded_knee_angle_deg": round(item.grounded_knee_angle_deg, 2),
        "grounded_vertical_deg": round(item.grounded_vertical_deg, 2),
        "raised_foot_horizontal_deg": round(item.raised_foot_horizontal_deg, 2),
        "left_elbow_angle_deg": round(item.left_elbow_angle_deg, 2),
        "right_elbow_angle_deg": round(item.right_elbow_angle_deg, 2),
        "head_yaw_ratio": round(item.head_yaw_ratio, 4),
        "head_tilt_deg": round(item.head_tilt_deg, 2),
        "score": frame_score.to_dict(),
        "output_image_path": image_rel_path,
    }


def _draw_annotations(frame: np.ndarray, metrics: SlowMarchFrameMetrics, frame_score: FrameScore) -> np.ndarray:
    rendered = frame.copy()

    def draw_leg(hip, knee, ankle, foot, color, label) -> None:
        pts = [(int(p[0]), int(p[1])) for p in (hip, knee, ankle, foot)]
        for a, b in zip(pts, pts[1:]):
            cv2.line(rendered, a, b, color, 2)
        cv2.circle(rendered, pts[1], 6, color, -1)
        cv2.circle(rendered, pts[2], 6, color, -1)
        cv2.putText(rendered, label, (pts[1][0] + 8, pts[1][1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    def draw_arm(shoulder, elbow, wrist, color) -> None:
        pts = [(int(p[0]), int(p[1])) for p in (shoulder, elbow, wrist)]
        cv2.line(rendered, pts[0], pts[1], color, 2)
        cv2.line(rendered, pts[1], pts[2], color, 2)
        cv2.circle(rendered, pts[1], 5, color, -1)

    grounded_is_left = metrics.grounded_leg == "left"
    # green = grounded leg, magenta = raised leg
    left_color = (0, 200, 0) if grounded_is_left else (255, 0, 255)
    right_color = (255, 0, 255) if grounded_is_left else (0, 200, 0)
    draw_leg(metrics.left_hip_px, metrics.left_knee_px, metrics.left_ankle_px, metrics.left_foot_px, left_color, "L")
    draw_leg(metrics.right_hip_px, metrics.right_knee_px, metrics.right_ankle_px, metrics.right_foot_px, right_color, "R")
    draw_arm(metrics.left_shoulder_px, metrics.left_elbow_px, metrics.left_wrist_px, (200, 200, 0))
    draw_arm(metrics.right_shoulder_px, metrics.right_elbow_px, metrics.right_wrist_px, (200, 200, 0))
    cv2.circle(rendered, (int(metrics.nose_px[0]), int(metrics.nose_px[1])), 4, (0, 255, 255), -1)

    gate = " [FOOT-GATE]" if frame_score.gated else ""
    label = (
        f"score {frame_score.total:.1f}/10{gate} | front {metrics.raised_leg} "
        f"foot {metrics.raised_foot_horizontal_deg:.0f}deg"
    )
    cv2.putText(rendered, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
    # foot_passing diagnostics (0 == ideal): both soles flat + legs together.
    passing = (
        f"hind-flat {metrics.hind_foot_flat_deg:.0f}  front-flat {metrics.front_foot_flat_deg:.0f}  "
        f"split {metrics.inter_leg_split_deg:.0f}deg"
    )
    cv2.putText(rendered, passing, (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
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
    annotated_dir = output_root / "key_frames"
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
    metrics: list[SlowMarchFrameMetrics] = []

    try:
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            # Analyze EVERY frame (subject to every_k_frames) — no fixed frame cap (PRD 2.2).
            if frame_index % config.every_k_frames != 0:
                frame_index += 1
                continue

            height, width = frame_bgr.shape[:2]
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            timestamp_ms = (frame_index / fps) * 1000.0

            result = holistic.detect_for_video(mp_image, int(timestamp_ms))
            processed_frames += 1

            frame_metrics = compute_frame_metrics(
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

    # Identify FRONT (driven) vs HIND (planted) leg by horizontal foot position for side
    # view; the front foot is scored for parallel-to-ground, the hind leg for straight +
    # perpendicular. Front view keeps the knee-lift assignment from compute_frame_metrics.
    if config.view == "side":
        assign_leg_roles_by_position(metrics)

    # Key frames = slow-march step extremes: front leg farthest forward + hind leg planted
    # (see key_frame_detection.find_step_peaks; signal selected by config.key_frame_signal).
    key_frames_metrics = find_step_peaks(metrics, config)

    key_frames: list[dict] = []
    frame_scores: list[float] = []

    for rank, item in enumerate(key_frames_metrics, start=1):
        frame_score = _score_frame_from_metrics(item, config)
        frame_scores.append(frame_score.total)

        image_rel_path = ""
        frame_bgr = _load_frame(video_path, item.frame_index)
        if frame_bgr is not None:
            file_base = f"step_{rank:02d}_frame_{item.frame_index:06d}_{item.raised_leg}"
            if config.save_annotated_frames:
                annotated = _draw_annotations(frame_bgr, item, frame_score)
                annotated_path = annotated_dir / f"{file_base}.jpg"
                cv2.imwrite(str(annotated_path), annotated)
                image_rel_path = str(annotated_path.relative_to(config.output_dir))
            if config.save_raw_frames:
                raw_path = raw_dir / f"{file_base}.jpg"
                cv2.imwrite(str(raw_path), frame_bgr)

        key_frames.append(_key_frame_to_json(rank, video_path.name, item, frame_score, image_rel_path))

    # iteration_count = number of detected key frames (PRD 2.3).
    iteration_count = len(key_frames)
    total_score = round(sum(frame_scores), 2)
    average_score = round(total_score / iteration_count, 2) if iteration_count else 0.0

    result_payload = {
        "video_name": video_path.name,
        "drill_type": "slow_march",
        "difficulty": config.difficulty,
        "view": config.view,
        "report_metadata": config.report_metadata.to_dict() if config.report_metadata else None,
        "summary": {
            "iteration_count": iteration_count,
            "total_score": total_score,
            "max_possible_score": iteration_count * 10,
            "average_score_per_step": average_score,
        },
        "peak_frames": key_frames,  # key name "peak_frames" reused for analyzer/report compatibility
    }

    result_json_path = output_root / "results.json"
    with result_json_path.open("w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2)

    report_pdf_path = output_root / "slow_march_report.pdf"
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
        "iteration_count": iteration_count,
        "peak_count": iteration_count,
        "total_score": total_score,
        "average_score": average_score,
        "difficulty": config.difficulty,
        "view": config.view,
        "results_json": str(result_json_path),
        "report_pdf": str(report_pdf_path),
    }


def run_pipeline(config: PipelineConfig) -> list[dict]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    videos = _iter_videos(config.input_path)
    if not videos:
        raise RuntimeError(f"No supported videos found at: {config.input_path}")

    return [process_video(video, config) for video in videos]
