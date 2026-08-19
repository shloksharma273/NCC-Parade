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
from .key_frame_detection import find_step_peaks
from .landmarks import TezChalFrameMetrics, compute_frame_metrics
from .mediapipe_models import ensure_models

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def _iter_videos(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [p for p in sorted(input_path.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]


def _key_frame_to_json(rank: int, video_name: str, item: TezChalFrameMetrics, image_rel_path: str) -> dict:
    return {
        "rank": rank,
        "video_name": video_name,
        "frame_index": item.frame_index,
        "timestamp_ms": round(item.timestamp_ms, 2),
        "inter_leg_angle_deg": round(item.inter_leg_angle_deg, 2),  # legs maximally split at the key frame
        "left_elbow_angle_deg": round(item.left_elbow_angle_deg, 2),
        "right_elbow_angle_deg": round(item.right_elbow_angle_deg, 2),
        "output_image_path": image_rel_path,
    }


def _draw_annotations(frame: np.ndarray, metrics: TezChalFrameMetrics) -> np.ndarray:
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

    label = f"inter-leg {metrics.inter_leg_angle_deg:.0f}deg  f#{metrics.frame_index}"
    cv2.putText(rendered, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
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

    key_frames: list[dict] = []
    montage_images: list[np.ndarray] = []
    montage_labels: list[str] = []

    for rank, item in enumerate(key_frames_metrics, start=1):
        image_rel_path = ""
        frame_bgr = _load_frame(video_path, item.frame_index)
        if frame_bgr is not None:
            file_base = f"step_{rank:02d}_frame_{item.frame_index:06d}"
            annotated = _draw_annotations(frame_bgr, item)
            if config.save_annotated_frames:
                annotated_path = annotated_dir / f"{file_base}.jpg"
                cv2.imwrite(str(annotated_path), annotated)
                image_rel_path = str(annotated_path.relative_to(config.output_dir))
            if config.save_raw_frames:
                cv2.imwrite(str(raw_dir / f"{file_base}.jpg"), frame_bgr)
            montage_images.append(annotated)
            montage_labels.append(f"#{rank} f{item.frame_index} {item.inter_leg_angle_deg:.0f}deg")

        key_frames.append(_key_frame_to_json(rank, video_path.name, item, image_rel_path))

    montage_rel = ""
    if config.save_montage and montage_images:
        montage = _build_montage(montage_images, montage_labels)
        if montage is not None:
            montage_path = output_root / "key_frames_montage.jpg"
            cv2.imwrite(str(montage_path), montage)
            montage_rel = str(montage_path.relative_to(config.output_dir))

    iteration_count = len(key_frames)
    result_payload = {
        "video_name": video_path.name,
        "drill_type": "tez_chal",
        "difficulty": config.difficulty,
        "view": config.view,
        "inter_leg_vector": config.inter_leg_vector,
        "report_metadata": config.report_metadata.to_dict() if config.report_metadata else None,
        "summary": {
            "iteration_count": iteration_count,
            "montage_image": montage_rel,
        },
        # NOTE: key frames only for now. Per-parameter scoring + PDF report is the next
        # step (HOOK) once the key-frame definition is confirmed on real footage.
        "peak_frames": key_frames,
    }

    result_json_path = output_root / "results.json"
    with result_json_path.open("w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2)

    return {
        "video": str(video_path),
        "processed_frames": processed_frames,
        "valid_scored_frames": valid_frames,
        "iteration_count": iteration_count,
        "peak_count": iteration_count,
        "difficulty": config.difficulty,
        "view": config.view,
        "results_json": str(result_json_path),
        "montage_image": str(output_root / "key_frames_montage.jpg") if montage_rel else "",
    }


def run_pipeline(config: PipelineConfig) -> list[dict]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    videos = _iter_videos(config.input_path)
    if not videos:
        raise RuntimeError(f"No supported videos found at: {config.input_path}")

    return [process_video(video, config) for video in videos]
