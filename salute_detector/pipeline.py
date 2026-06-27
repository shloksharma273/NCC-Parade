from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HolisticLandmarker,
    HolisticLandmarkerOptions,
    HolisticLandmarkerResult,
    RunningMode,
)
from mediapipe.tasks.python.vision.hand_landmarker import HandLandmark

from .config import PipelineConfig
from .landmarks import FrameMetrics, get_eye_scale, get_eyebrow_anchor
from .mediapipe_models import ensure_models
from .posture import (
    analyze_posture_for_frames,
    is_front_salute_video,
    save_posture_results,
)

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
INDEX_FINGER_TIP = int(HandLandmark.INDEX_FINGER_TIP)


def _iter_videos(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [p for p in sorted(input_path.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]


def _right_index_tip(result: HolisticLandmarkerResult, width: int, height: int) -> Optional[np.ndarray]:
    if not result.right_hand_landmarks:
        return None
    tip = result.right_hand_landmarks[INDEX_FINGER_TIP]
    return np.array([tip.x * width, tip.y * height], dtype=float)


def _draw_annotations(
    frame: np.ndarray, right_index_point: tuple[float, float], eyebrow_anchor: tuple[float, float]
) -> np.ndarray:
    rendered = frame.copy()
    p1 = (int(right_index_point[0]), int(right_index_point[1]))
    p2 = (int(eyebrow_anchor[0]), int(eyebrow_anchor[1]))
    cv2.circle(rendered, p1, 6, (0, 255, 255), -1)
    cv2.circle(rendered, p2, 6, (255, 255, 0), -1)
    cv2.line(rendered, p1, p2, (0, 200, 0), 2)
    return rendered


def _temporal_suppress(candidates: list[FrameMetrics], window: int, top_n: int) -> list[FrameMetrics]:
    if window <= 0:
        return candidates[:top_n]

    selected: list[FrameMetrics] = []
    for candidate in sorted(candidates, key=lambda x: x.distance_normalized):
        if any(abs(candidate.frame_index - s.frame_index) <= window for s in selected):
            continue
        selected.append(candidate)
        if len(selected) >= top_n:
            break
    return selected


def process_video(video_path: Path, config: PipelineConfig) -> dict:
    output_root = config.output_dir / video_path.stem
    output_root.mkdir(parents=True, exist_ok=True)
    annotated_dir = output_root / "annotated_frames"
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
        min_face_detection_confidence=config.min_detection_confidence,
        min_face_landmarks_confidence=config.min_detection_confidence,
        min_hand_landmarks_confidence=config.min_detection_confidence,
        min_pose_detection_confidence=config.min_detection_confidence,
        min_pose_landmarks_confidence=config.min_detection_confidence,
        output_face_blendshapes=False,
        output_segmentation_mask=False,
    )
    holistic = HolisticLandmarker.create_from_options(holistic_options)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_index = 0
    processed_frames = 0
    valid_frames = 0
    metrics: list[FrameMetrics] = []
    frame_cache: dict[int, np.ndarray] = {}

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
            timestamp_ms = int((frame_index / fps) * 1000.0)

            result = holistic.detect_for_video(mp_image, timestamp_ms)
            processed_frames += 1

            if not result.face_landmarks:
                frame_index += 1
                continue

            right_index_tip = _right_index_tip(result, width, height)
            eyebrow_anchor = get_eyebrow_anchor(result.face_landmarks, width, height)
            eye_scale = get_eye_scale(result.face_landmarks, width, height)

            if right_index_tip is None or eyebrow_anchor is None or eye_scale is None:
                frame_index += 1
                continue

            raw_distance = float(np.linalg.norm(right_index_tip - eyebrow_anchor))
            normalized_distance = raw_distance / eye_scale

            frame_metric = FrameMetrics(
                frame_index=frame_index,
                timestamp_ms=timestamp_ms,
                distance_raw=raw_distance,
                distance_normalized=normalized_distance,
                detection_confidence=1.0,
                right_index_point_px=(float(right_index_tip[0]), float(right_index_tip[1])),
                eyebrow_anchor_px=(float(eyebrow_anchor[0]), float(eyebrow_anchor[1])),
            )
            metrics.append(frame_metric)
            frame_cache[frame_index] = frame_bgr
            valid_frames += 1
            frame_index += 1
    finally:
        cap.release()
        holistic.close()

    ranked = sorted(metrics, key=lambda x: x.distance_normalized)
    selected = _temporal_suppress(ranked, config.temporal_nms_window, config.top_n)

    selected_rows = []
    for rank, item in enumerate(selected, start=1):
        image_rel_path = ""
        frame_bgr = frame_cache.get(item.frame_index)
        if frame_bgr is not None:
            file_base = f"rank_{rank:02d}_frame_{item.frame_index:06d}"
            if config.save_annotated_frames:
                annotated = _draw_annotations(frame_bgr, item.right_index_point_px, item.eyebrow_anchor_px)
                annotated_path = annotated_dir / f"{file_base}.jpg"
                cv2.imwrite(str(annotated_path), annotated)
                image_rel_path = str(annotated_path.relative_to(config.output_dir))
            if config.save_raw_frames:
                raw_path = raw_dir / f"{file_base}.jpg"
                cv2.imwrite(str(raw_path), frame_bgr)

        selected_rows.append(
            {
                "rank": rank,
                "video_name": video_path.name,
                "frame_index": item.frame_index,
                "timestamp_ms": round(item.timestamp_ms, 2),
                "distance_raw": item.distance_raw,
                "distance_normalized": item.distance_normalized,
                "detection_confidence": item.detection_confidence,
                "output_image_path": image_rel_path,
            }
        )

    result_json_path = output_root / "results.json"
    result_csv_path = output_root / "results.csv"
    with result_json_path.open("w", encoding="utf-8") as f:
        json.dump(selected_rows, f, indent=2)
    with result_csv_path.open("w", encoding="utf-8", newline="") as f:
        if selected_rows:
            writer = csv.DictWriter(f, fieldnames=list(selected_rows[0].keys()))
            writer.writeheader()
            writer.writerows(selected_rows)

    summary = {
        "video": str(video_path),
        "processed_frames": processed_frames,
        "valid_scored_frames": valid_frames,
        "selected_count": len(selected_rows),
        "results_json": str(result_json_path),
        "results_csv": str(result_csv_path),
        "posture_analysis_json": None,
        "posture_analysis_csv": None,
    }

    if config.enable_posture_analysis and (
        config.force_posture_analysis or is_front_salute_video(video_path)
    ) and selected:
        posture_analyses = analyze_posture_for_frames(
            video_path=video_path,
            selected_frames=selected,
            output_root=output_root,
            output_dir=config.output_dir,
            min_confidence=config.min_detection_confidence,
            difficulty=config.difficulty,
            posture_top_n=config.posture_top_n,
        )
        posture_json, posture_csv = save_posture_results(posture_analyses, output_root)
        summary["posture_analysis_json"] = str(posture_json)
        summary["posture_analysis_csv"] = str(posture_csv)

    return summary


def run_pipeline(config: PipelineConfig) -> list[dict]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    videos = _iter_videos(config.input_path)
    if not videos:
        raise RuntimeError(f"No supported videos found at: {config.input_path}")

    return [process_video(video, config) for video in videos]
