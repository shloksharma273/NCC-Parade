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
from .landmarks import HillMarchFrameMetrics, compute_frame_metrics
from .mediapipe_models import ensure_models
from .report import generate_pdf_report
from .scoring import FrameScore, score_frame

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def _iter_videos(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return [p for p in sorted(input_path.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]


def _score_frame_from_metrics(item: HillMarchFrameMetrics, config: PipelineConfig) -> FrameScore:
    # Parameter-1 full-marks threshold depends on the camera view (front 50 / side 70).
    legs_apart_full_deg = (
        config.legs_apart_full_deg_front if config.view == "front" else config.legs_apart_full_deg_side
    )
    return score_frame(
        inter_leg_angle_deg=item.inter_leg_angle_deg,
        left_elbow_angle_deg=item.left_elbow_angle_deg,
        right_elbow_angle_deg=item.right_elbow_angle_deg,
        left_arm_abduction_deg=item.left_arm_abduction_deg,
        right_arm_abduction_deg=item.right_arm_abduction_deg,
        left_knee_angle_deg=item.left_knee_angle_deg,
        right_knee_angle_deg=item.right_knee_angle_deg,
        head_yaw_ratio=item.head_yaw_ratio,
        head_tilt_deg=item.head_tilt_deg,
        difficulty=config.difficulty,
        legs_apart_full_deg=legs_apart_full_deg,
        target_arm_angle_deg=config.target_arm_angle_deg,
        target_knee_angle_deg=config.target_knee_angle_deg,
        target_head_tilt_deg=config.target_head_tilt_deg,
    )


def _key_frame_to_json(rank: int, video_name: str, item: HillMarchFrameMetrics, frame_score: FrameScore, image_rel_path: str) -> dict:
    return {
        "rank": rank,
        "video_name": video_name,
        "frame_index": item.frame_index,
        "timestamp_ms": round(item.timestamp_ms, 2),
        "inter_leg_angle_deg": round(item.inter_leg_angle_deg, 2),  # separation between legs (key signal + param 1)
        "left_elbow_angle_deg": round(item.left_elbow_angle_deg, 2),
        "right_elbow_angle_deg": round(item.right_elbow_angle_deg, 2),
        "left_arm_abduction_deg": round(item.left_arm_abduction_deg, 2),
        "right_arm_abduction_deg": round(item.right_arm_abduction_deg, 2),
        "left_knee_angle_deg": round(item.left_knee_angle_deg, 2),
        "right_knee_angle_deg": round(item.right_knee_angle_deg, 2),
        "head_yaw_ratio": round(item.head_yaw_ratio, 4),
        "head_tilt_deg": round(item.head_tilt_deg, 2),
        "score": frame_score.to_dict(),
        "output_image_path": image_rel_path,
    }


def _draw_annotations(frame: np.ndarray, m: HillMarchFrameMetrics, s: FrameScore) -> np.ndarray:
    rendered = frame.copy()

    def draw_chain(pts, color) -> None:
        p = [(int(x[0]), int(x[1])) for x in pts]
        for a, b in zip(p, p[1:]):
            cv2.line(rendered, a, b, color, 2)
        for pt in p:
            cv2.circle(rendered, pt, 5, color, -1)

    # cyan = left leg, magenta = right leg, yellow = arms
    draw_chain([m.left_hip_px, m.left_knee_px, m.left_ankle_px, m.left_foot_px], (255, 255, 0))
    draw_chain([m.right_hip_px, m.right_knee_px, m.right_ankle_px, m.right_foot_px], (255, 0, 255))
    draw_chain([m.left_shoulder_px, m.left_elbow_px, m.left_wrist_px], (0, 200, 255))
    draw_chain([m.right_shoulder_px, m.right_elbow_px, m.right_wrist_px], (0, 200, 255))
    cv2.circle(rendered, (int(m.nose_px[0]), int(m.nose_px[1])), 4, (0, 255, 255), -1)

    cv2.putText(rendered, f"score {s.total:.1f}/10  sep {m.inter_leg_angle_deg:.0f}deg  f#{m.frame_index}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(rendered, f"apart {s.legs_apart:.0f}  arms {s.arms:.0f}  legs {s.legs_straight:.0f}  head {s.head_straight:.0f}",
                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 255), 2, cv2.LINE_AA)
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
    if not images:
        return None
    tiles = []
    for img, label in zip(images, labels):
        h, w = img.shape[:2]
        tile = cv2.resize(img, (tile_w, int(h * (tile_w / w))))
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
    metrics: list[HillMarchFrameMetrics] = []

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

    # Key frames = hill-march step extremes: inter-leg separation at a local maximum.
    key_frames_metrics = find_step_peaks(metrics, config)

    key_frames: list[dict] = []
    frame_scores: list[float] = []
    montage_images: list[np.ndarray] = []
    montage_labels: list[str] = []

    for rank, item in enumerate(key_frames_metrics, start=1):
        frame_score = _score_frame_from_metrics(item, config)
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

        key_frames.append(_key_frame_to_json(rank, video_path.name, item, frame_score, image_rel_path))

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
        "drill_type": "hill_march",
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
        "peak_frames": key_frames,  # key name "peak_frames" reused for report/analyzer compatibility
    }

    result_json_path = output_root / "results.json"
    with result_json_path.open("w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2)

    report_pdf_path = output_root / "hill_march_report.pdf"
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
