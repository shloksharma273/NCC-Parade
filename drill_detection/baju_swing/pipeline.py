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

from .config import FRONT_VIEW, FRONT_WEIGHTS, WEIGHTS, PipelineConfig
from .hand_analysis import HandScore, analyze_hands_for_frames
from .key_frame_detection import find_swing_peaks
from .landmarks import BajuSwingFrameMetrics, compute_frame_metrics
from .mediapipe_models import ensure_models
from .report import generate_pdf_report
from .scoring import FrameScore, score_fist_height, score_swing_frame
from .signals import build_key_frame_signal

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def _iter_videos(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [p for p in sorted(input_path.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]


def _key_frame_to_json(
    rank: int,
    video_name: str,
    view: str,
    item: BajuSwingFrameMetrics,
    hand: HandScore,
    frame_score: FrameScore,
    image_rel_path: str,
) -> dict:
    return {
        "rank": rank,
        "video_name": video_name,
        "view": view,
        "frame_index": item.frame_index,
        "timestamp_ms": round(item.timestamp_ms, 2),
        "inter_arm_angle_deg": round(item.inter_arm_angle_deg, 2),
        # Raw front-view metrics (reported for scoring calibration): fist height
        # above hip in shoulder-width units (swing spread, §10.2) and the
        # fingers-together midpoint spread (fist, §10.3).
        "fist_height_norm": round(item.fist_height_norm, 3),
        "fingers_together_spread": (
            None if hand.fingers_together_spread != hand.fingers_together_spread
            else round(hand.fingers_together_spread, 3)
        ),
        "left_elbow_angle_deg": round(item.left_elbow_angle_deg, 2),
        "right_elbow_angle_deg": round(item.right_elbow_angle_deg, 2),
        "left_knee_angle_deg": round(item.left_knee_angle_deg, 2),
        "right_knee_angle_deg": round(item.right_knee_angle_deg, 2),
        "hands_detected": hand.hands_detected,
        "score": frame_score.to_dict(),
        "output_image_path": image_rel_path,
    }


def _draw_annotations(
    frame: np.ndarray,
    metrics: BajuSwingFrameMetrics,
    hand: HandScore,
    frame_score: FrameScore,
    view: str,
) -> np.ndarray:
    rendered = frame.copy()

    def line(p1: tuple[float, float], p2: tuple[float, float], color, thickness=2) -> None:
        cv2.line(rendered, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), color, thickness)

    def dot(p: tuple[float, float], color, r=5) -> None:
        cv2.circle(rendered, (int(p[0]), int(p[1])), r, color, -1)

    # Arms (front-back marching swing: one forward, one back).
    line(metrics.left_shoulder_px, metrics.left_elbow_px, (255, 180, 0))
    line(metrics.left_elbow_px, metrics.left_wrist_px, (255, 180, 0))
    dot(metrics.left_elbow_px, (255, 180, 0))
    dot(metrics.left_wrist_px, (255, 180, 0))
    line(metrics.right_shoulder_px, metrics.right_elbow_px, (0, 180, 255))
    line(metrics.right_elbow_px, metrics.right_wrist_px, (0, 180, 255))
    dot(metrics.right_elbow_px, (0, 180, 255))
    dot(metrics.right_wrist_px, (0, 180, 255))
    # Inter-arm spread: shoulder-midpoint to each wrist.
    shoulder_mid = (
        (metrics.left_shoulder_px[0] + metrics.right_shoulder_px[0]) / 2.0,
        (metrics.left_shoulder_px[1] + metrics.right_shoulder_px[1]) / 2.0,
    )
    line(shoulder_mid, metrics.left_wrist_px, (0, 255, 0), 1)
    line(shoulder_mid, metrics.right_wrist_px, (0, 255, 0), 1)

    # Legs.
    line(metrics.left_hip_px, metrics.left_knee_px, (200, 200, 0))
    line(metrics.left_knee_px, metrics.left_ankle_px, (200, 200, 0))
    line(metrics.right_hip_px, metrics.right_knee_px, (200, 200, 0))
    line(metrics.right_knee_px, metrics.right_ankle_px, (200, 200, 0))

    # Fingertips (from IMAGE-mode hand pass) if available.
    for tip in hand.fingertips_px:
        dot(tip, (0, 255, 255), 3)

    # FRONT view: mark the higher fist and its height above the hip line (the
    # swing-spread metric); draw the hip reference line.
    if view == FRONT_VIEW:
        higher_wrist = (
            metrics.left_wrist_px
            if metrics.left_wrist_px[1] <= metrics.right_wrist_px[1]
            else metrics.right_wrist_px
        )
        hip_y = (metrics.left_hip_px[1] + metrics.right_hip_px[1]) / 2.0
        line(metrics.left_hip_px, metrics.right_hip_px, (0, 200, 0), 1)  # hip reference
        line((higher_wrist[0], hip_y), higher_wrist, (0, 255, 0), 2)     # fist height
        dot(higher_wrist, (255, 0, 255), 6)
        spread_detail = f"fist-height {metrics.fist_height_norm:.2f}sw"
        fist_label = "Fingers together"
    else:
        spread_detail = f"inter-arm {metrics.inter_arm_angle_deg:.0f} deg"
        fist_label = "Fist closed"

    lines = [f"Baju Swing [{view}]  score {frame_score.total:.1f}/10"]
    if frame_score.arms_straight is not None:
        lines.append(f"Arms straight: {frame_score.arms_straight:.1f}/10  (fwd/back swing)")
    lines += [
        f"Swing spread: {frame_score.swing_spread:.1f}/10  ({spread_detail})",
        f"Legs straight: {frame_score.legs_straight:.1f}/10",
        f"{fist_label}: {frame_score.fist:.1f}/10   Thumb on top: {frame_score.thumb:.1f}/10",
    ]
    y = 26
    for text in lines:
        cv2.putText(rendered, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(rendered, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1, cv2.LINE_AA)
        y += 24
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
    annotated_dir = output_root / "swing_frames"
    raw_dir = output_root / "raw_frames"
    if config.save_annotated_frames:
        annotated_dir.mkdir(parents=True, exist_ok=True)
    if config.save_raw_frames:
        raw_dir.mkdir(parents=True, exist_ok=True)

    model_path = ensure_models()

    # ------------------------------------------------------------------
    # Pass 1: pose in VIDEO mode over EVERY frame (subject to every_k_frames)
    # to build the inter-arm-angle signal and find swing key frames (§2.2/§3).
    # ------------------------------------------------------------------
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
    metrics: list[BajuSwingFrameMetrics] = []

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

    # Key-frame signal is view-dependent (§10.1): side = inter-arm angle,
    # front = height of the higher fist. The peak finder is view-agnostic.
    signal = build_key_frame_signal(metrics, config.view)
    prominence_floor = (
        config.min_peak_prominence_floor_front
        if config.view == FRONT_VIEW
        else config.min_peak_prominence_floor_side
    )
    key_frames_metrics = find_swing_peaks(
        metrics,
        signal=signal,
        smooth_window=config.smooth_window,
        min_distance=config.min_peak_distance_frames,
        min_prominence_abs=config.min_peak_prominence_deg,
        min_prominence_ratio=config.min_peak_prominence_ratio,
        min_prominence_floor=prominence_floor,
    )

    # ------------------------------------------------------------------
    # Pass 2: IMAGE-mode Holistic on the selected key frames for hands (§3).
    # ------------------------------------------------------------------
    hand_scores = analyze_hands_for_frames(
        video_path=video_path,
        frame_indices=[m.frame_index for m in key_frames_metrics],
        min_confidence=config.min_detection_confidence,
        difficulty=config.difficulty,
        view=config.view,
    )

    weights = FRONT_WEIGHTS if config.view == FRONT_VIEW else WEIGHTS

    key_frames: list[dict] = []
    frame_totals: list[float] = []

    for rank, item in enumerate(key_frames_metrics, start=1):
        hand = hand_scores.get(item.frame_index, HandScore(item.frame_index, 0.0, 0.0, 0))
        # FRONT view: swing spread = scored hand-tip separation (§10.2). SIDE
        # view leaves it None so scoring uses the inter-arm angle.
        # FRONT view: swing spread = pre-scored fist height (§10.2). SIDE view
        # leaves it None so scoring uses the inter-arm angle.
        swing_spread_score = None
        if config.view == FRONT_VIEW:
            swing_spread_score = score_fist_height(item.fist_height_norm, config.difficulty)
        frame_score = score_swing_frame(
            inter_arm_angle_deg=item.inter_arm_angle_deg,
            left_elbow_angle_deg=item.left_elbow_angle_deg,
            right_elbow_angle_deg=item.right_elbow_angle_deg,
            left_knee_angle_deg=item.left_knee_angle_deg,
            right_knee_angle_deg=item.right_knee_angle_deg,
            fist_score=hand.fist_score,
            thumb_score=hand.thumb_score,
            difficulty=config.difficulty,
            target_arm_angle_deg=config.target_arm_angle_deg,
            target_inter_arm_angle_deg=config.target_inter_arm_angle_deg,
            target_knee_angle_deg=config.target_knee_angle_deg,
            weights=weights,
            swing_spread_score=swing_spread_score,
        )
        frame_totals.append(frame_score.total)

        image_rel_path = ""
        frame_bgr = _load_frame(video_path, item.frame_index)
        if frame_bgr is not None:
            file_base = f"swing_{rank:02d}_frame_{item.frame_index:06d}"
            if config.save_annotated_frames:
                annotated = _draw_annotations(frame_bgr, item, hand, frame_score, config.view)
                annotated_path = annotated_dir / f"{file_base}.jpg"
                cv2.imwrite(str(annotated_path), annotated)
                image_rel_path = str(annotated_path.relative_to(config.output_dir))
            if config.save_raw_frames:
                raw_path = raw_dir / f"{file_base}.jpg"
                cv2.imwrite(str(raw_path), frame_bgr)

        key_frames.append(
            _key_frame_to_json(
                rank, video_path.name, config.view, item, hand, frame_score, image_rel_path
            )
        )

    # Aggregation (§6.7): iteration_count = number of key frames.
    iteration_count = len(key_frames)
    total_score = round(sum(frame_totals), 2)
    average_score = round(total_score / iteration_count, 2) if iteration_count else 0.0

    result_payload = {
        "video_name": video_path.name,
        "view": config.view,
        "difficulty": config.difficulty,
        "report_metadata": config.report_metadata.to_dict() if config.report_metadata else None,
        "summary": {
            "iteration_count": iteration_count,          # = number of detected swings
            "total_score": total_score,                  # sum of per-swing totals
            "max_possible_score": iteration_count * 10,  # iteration_count * 10
            "average_score_per_swing": average_score,    # total_score / iteration_count
        },
        "key_frames": key_frames,
    }

    result_json_path = output_root / "results.json"
    with result_json_path.open("w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2)

    report_pdf_path = output_root / "baju_swing_report.pdf"
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
        "swing_count": iteration_count,
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
