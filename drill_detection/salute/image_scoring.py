from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp

from .difficulty import DifficultyProfile
from .posture import _create_image_landmarker, analyze_posture, draw_posture_annotations

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class ImageScoreResult:
    image_id: str
    source_image: str
    annotated_image: str
    result_json: str
    payload: dict


def _iter_images(input_dir: Path) -> list[Path]:
    return sorted(
        p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )


def _image_id(image_path: Path) -> str:
    return image_path.stem


def build_score_payload(image_id: str, metrics: dict[str, float]) -> dict:
    return {
        "image_id": image_id,
        "total_score": round(float(metrics["weighted_score"]), 2),
        "section_scores": {
            "fingers_joined": round(float(metrics["fingers_joined_score"]), 2),
            "elbow_angle": round(float(metrics["elbow_angle_score"]), 2),
            "heels": round(float(metrics["heels_score"]), 2),
            "left_hand_attached": round(float(metrics["left_hand_attached_score"]), 2),
        },
    }


def score_image_file(
    image_path: Path,
    output_dir: Path,
    profile: DifficultyProfile,
    min_confidence: float,
) -> ImageScoreResult:
    image_id = _image_id(image_path)
    annotated_dir = output_dir / "annotated"
    results_dir = output_dir / "results"
    annotated_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    frame_bgr = cv2.imread(str(image_path))
    if frame_bgr is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    height, width = frame_bgr.shape[:2]
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

    holistic = _create_image_landmarker(min_confidence)
    try:
        result = holistic.detect(mp_image)
        metrics = analyze_posture(result, width, height, profile)
        annotated = draw_posture_annotations(frame_bgr, result, metrics)
        payload = build_score_payload(image_id, metrics)
    finally:
        holistic.close()

    annotated_path = annotated_dir / f"{image_id}_scored.jpg"
    cv2.imwrite(str(annotated_path), annotated)

    json_path = results_dir / f"{image_id}.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return ImageScoreResult(
        image_id=image_id,
        source_image=str(image_path),
        annotated_image=str(annotated_path),
        result_json=str(json_path),
        payload=payload,
    )


def score_images_in_folder(
    input_dir: Path,
    output_dir: Path,
    difficulty: float,
    min_confidence: float = 0.5,
) -> list[ImageScoreResult]:
    images = _iter_images(input_dir)
    if not images:
        raise RuntimeError(f"No supported images found in: {input_dir}")

    profile = DifficultyProfile.load(override=difficulty)
    results: list[ImageScoreResult] = []

    for image_path in images:
        try:
            results.append(
                score_image_file(
                    image_path=image_path,
                    output_dir=output_dir,
                    profile=profile,
                    min_confidence=min_confidence,
                )
            )
        except Exception as exc:
            image_id = _image_id(image_path)
            error_payload = {
                "image_id": image_id,
                "total_score": None,
                "section_scores": None,
                "error": str(exc),
            }
            results_dir = output_dir / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            json_path = results_dir / f"{image_id}.json"
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(error_payload, f, indent=2)
            results.append(
                ImageScoreResult(
                    image_id=image_id,
                    source_image=str(image_path),
                    annotated_image="",
                    result_json=str(json_path),
                    payload=error_payload,
                )
            )

    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump([item.payload for item in results], f, indent=2)

    return results


def seed_test_images(source_dir: Path, test_images_dir: Path) -> int:
    test_images_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for image_path in _iter_images(source_dir):
        dest = test_images_dir / image_path.name
        if dest.exists():
            continue
        shutil.copy2(image_path, dest)
        copied += 1
    return copied
