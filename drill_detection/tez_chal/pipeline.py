from __future__ import annotations

import json
import math
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
from .hand_analysis import analyze_hands_for_frames
from .key_frame_detection import find_step_peaks
from .landmarks import TezChalFrameMetrics, compute_frame_metrics
from .mediapipe_models import ensure_models
from .report import generate_pdf_report
from .scoring import FrameScore, score_frame

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def _iter_videos(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [p for p in sorted(input_path.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]


def _key_frame_to_json(
    rank: int,
    video_name: str,
    item: TezChalFrameMetrics,
    frame_score: FrameScore,
    image_rel_path: str,
    fist_samples_with_hands: int,
    fist_samples_total: int,
) -> dict:
    return {
        "rank": rank,
        "video_name": video_name,
        "frame_index": item.frame_index,
        "timestamp_ms": round(item.timestamp_ms, 2),
        "inter_leg_angle_deg": round(item.inter_leg_angle_deg, 2),  # legs maximally split at the key frame
        "left_elbow_angle_deg": round(item.left_elbow_angle_deg, 2),
        "right_elbow_angle_deg": round(item.right_elbow_angle_deg, 2),
        "left_knee_angle_deg": round(item.left_knee_angle_deg, 2),
        "right_knee_angle_deg": round(item.right_knee_angle_deg, 2),
        "fist_samples_with_hands": fist_samples_with_hands,  # frames near the key frame that had a detectable hand
        "fist_samples_total": fist_samples_total,
        "score": frame_score.to_dict(),
        "output_image_path": image_rel_path,
    }


def _draw_annotations(frame: np.ndarray, metrics: TezChalFrameMetrics, frame_score: FrameScore) -> np.ndarray:
    rendered = frame.copy()

    def draw_leg(hip, knee, ankle, foot, color, label) -> None:
        pts = [(int(p[0]), int(p[1])) for p in (hip, knee, ankle, foot)]
        for a, b in zip(pts, pts[1:]):
            cv2.line(rendered, a, b, color, 2)
        cv2.circle(rendered, pts[0], 5, color, -1)
        cv2.circle(rendered, pts[1], 6, color, -1)
        cv2.circle(rendered, pts[2], 6, color, -1)
        cv2.putText(rendered, label, (pts[1][0] + 8, pts[1][1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    def draw_arm(shoulder, elbow, wrist, color) -> None:
        pts = [(int(p[0]), int(p[1])) for p in (shoulder, elbow, wrist)]
        cv2.line(rendered, pts[0], pts[1], color, 2)
        cv2.line(rendered, pts[1], pts[2], color, 2)
        cv2.circle(rendered, pts[1], 5, color, -1)

    # cyan = left leg, magenta = right leg
    draw_leg(metrics.left_hip_px, metrics.left_knee_px, metrics.left_ankle_px, metrics.left_foot_px, (255, 255, 0), "L")
    draw_leg(metrics.right_hip_px, metrics.right_knee_px, metrics.right_ankle_px, metrics.right_foot_px, (255, 0, 255), "R")
    draw_arm(metrics.left_shoulder_px, metrics.left_elbow_px, metrics.left_wrist_px, (200, 200, 0))
    draw_arm(metrics.right_shoulder_px, metrics.right_elbow_px, metrics.right_wrist_px, (200, 200, 0))
    cv2.circle(rendered, (int(metrics.nose_px[0]), int(metrics.nose_px[1])), 4, (0, 255, 255), -1)

    label = f"score {frame_score.total:.1f}/10  f#{metrics.frame_index}"
    cv2.putText(rendered, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
    breakdown = (
        f"arms {frame_score.arms_straight:.0f}  legs {frame_score.legs_straight:.0f}  "
        f"fist {frame_score.fist_closed:.0f}"
    )
    cv2.putText(rendered, breakdown, (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
    return rendered


def _load_frame(video_path: Path, frame_index: int) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def _build_montage(images: list[np.ndarray], labels: list[str], tile_w: int = 240) -> np.ndarray | None:
    """Tile the annotated key frames into a single grid image for quick review."""
    if not images:
        return None
    tiles = []
    for img, label in zip(images, labels):
        h, w = img.shape[:2]
        tile_h = int(h * (tile_w / w))
        tile = cv2.resize(img, (tile_w, tile_h))
        cv2.rectangle(tile, (0, 0), (tile_w, 22), (0, 0, 0), -1)
        cv2.putText(tile, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)

    cols = min(len(tiles), 5)
    rows = math.ceil(len(tiles) / cols)
    cell_h = max(t.shape[0] for t in tiles)
    grid = np.zeros((rows * cell_h, cols * tile_w, 3), dtype=np.uint8)
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        grid[r * cell_h : r * cell_h + tile.shape[0], c * tile_w : (c + 1) * tile_w] = tile
    return grid


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
    metrics: list[TezChalFrameMetrics] = []

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
                inter_leg_vector=config.inter_leg_vector,
            )
            if frame_metrics is not None:
                metrics.append(frame_metrics)
                valid_frames += 1

            frame_index += 1
    finally:
        cap.release()
        holistic.close()

    # Key frames = quick-march step extremes: inter-leg angle at a local maximum.
    key_frames_metrics = find_step_peaks(metrics, config)

    # Pass 2: re-run Holistic in IMAGE mode on the key frames only, for reliable hand
    # landmarks -> the fist-closed score (the first pass runs in VIDEO mode, where hands
    # are unreliable). Mirrors baju_swing / salute.
    hand_scores = analyze_hands_for_frames(
        video_path,
        [m.frame_index for m in key_frames_metrics],
        min_confidence=config.hand_min_confidence,
        difficulty=config.difficulty,
        snap_window=config.hand_snap_window,
        snap_step=config.hand_snap_step,
        frame_count=frame_index,  # total frames read (upper bound for clamping the snap window)
    )

    key_frames: list[dict] = []
    frame_scores: list[float] = []
    montage_images: list[np.ndarray] = []
    montage_labels: list[str] = []

    for rank, item in enumerate(key_frames_metrics, start=1):
        hand = hand_scores.get(item.frame_index)
        frame_score = score_frame(
            left_elbow_angle_deg=item.left_elbow_angle_deg,
            right_elbow_angle_deg=item.right_elbow_angle_deg,
            left_knee_angle_deg=item.left_knee_angle_deg,
            right_knee_angle_deg=item.right_knee_angle_deg,
            fist_closed_score=hand.fist_score if hand else 0.0,
            hands_detected=hand.hands_detected if hand else 0,
            difficulty=config.difficulty,
            target_arm_angle_deg=config.target_arm_angle_deg,
            target_knee_angle_deg=config.target_knee_angle_deg,
        )
        frame_scores.append(frame_score.total)

        image_rel_path = ""
        frame_bgr = _load_frame(video_path, item.frame_index)
        if frame_bgr is not None:
            file_base = f"step_{rank:02d}_frame_{item.frame_index:06d}"
            annotated = _draw_annotations(frame_bgr, item, frame_score)
            if config.save_annotated_frames:
                annotated_path = annotated_dir / f"{file_base}.jpg"
                cv2.imwrite(str(annotated_path), annotated)
                image_rel_path = str(annotated_path.relative_to(config.output_dir))
            if config.save_raw_frames:
                cv2.imwrite(str(raw_dir / f"{file_base}.jpg"), frame_bgr)
            montage_images.append(annotated)
            montage_labels.append(f"#{rank} f{item.frame_index} {frame_score.total:.1f}/10")

        key_frames.append(_key_frame_to_json(
            rank, video_path.name, item, frame_score, image_rel_path,
            fist_samples_with_hands=hand.samples_with_hands if hand else 0,
            fist_samples_total=hand.samples_total if hand else 0,
        ))

    montage_rel = ""
    if config.save_montage and montage_images:
        montage = _build_montage(montage_images, montage_labels)
        if montage is not None:
            montage_path = output_root / "key_frames_montage.jpg"
            cv2.imwrite(str(montage_path), montage)
            montage_rel = str(montage_path.relative_to(config.output_dir))

    iteration_count = len(key_frames)
    total_score = round(sum(frame_scores), 2)
    average_score = round(total_score / iteration_count, 2) if iteration_count else 0.0

    result_payload = {
        "video_name": video_path.name,
        "drill_type": "tez_chal",
        "difficulty": config.difficulty,
        "view": config.view,
        "inter_leg_vector": config.inter_leg_vector,
        "report_metadata": config.report_metadata.to_dict() if config.report_metadata else None,
        "summary": {
            "iteration_count": iteration_count,
            "total_score": total_score,
            "max_possible_score": iteration_count * 10,
            "average_score_per_step": average_score,
            "montage_image": montage_rel,
        },
        "peak_frames": key_frames,  # key name "peak_frames" reused for report compatibility
    }

    result_json_path = output_root / "results.json"
    with result_json_path.open("w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2)

    report_pdf_path = output_root / "tez_chal_report.pdf"
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
        "montage_image": str(output_root / "key_frames_montage.jpg") if montage_rel else "",
    }


def run_pipeline(config: PipelineConfig) -> list[dict]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    videos = _iter_videos(config.input_path)
    if not videos:
        raise RuntimeError(f"No supported videos found at: {config.input_path}")

    return [process_video(video, config) for video in videos]
