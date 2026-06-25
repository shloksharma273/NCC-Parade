from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


RIGHT_EYEBROW_IDX = [70, 63, 105, 66, 107]
LEFT_EYEBROW_IDX = [336, 296, 334, 293, 300]
LEFT_EYE_CENTER_IDX = [33, 133]
RIGHT_EYE_CENTER_IDX = [362, 263]


@dataclass
class FrameMetrics:
    frame_index: int
    timestamp_ms: float
    distance_raw: float
    distance_normalized: float
    detection_confidence: float
    right_index_point_px: tuple[float, float]
    eyebrow_anchor_px: tuple[float, float]


def _mean_point(points: list[np.ndarray]) -> Optional[np.ndarray]:
    if not points:
        return None
    return np.mean(np.stack(points, axis=0), axis=0)


def _face_point(face_landmarks, indices: list[int], width: int, height: int) -> Optional[np.ndarray]:
    points: list[np.ndarray] = []
    for idx in indices:
        lm = face_landmarks[idx]
        points.append(np.array([lm.x * width, lm.y * height], dtype=float))
    return _mean_point(points)


def get_eyebrow_anchor(face_landmarks, width: int, height: int) -> Optional[np.ndarray]:
    right = _face_point(face_landmarks, RIGHT_EYEBROW_IDX, width, height)
    left = _face_point(face_landmarks, LEFT_EYEBROW_IDX, width, height)
    if right is None and left is None:
        return None
    if right is None:
        return left
    if left is None:
        return right
    return (right + left) / 2.0


def get_eye_scale(face_landmarks, width: int, height: int) -> Optional[float]:
    left_center = _face_point(face_landmarks, LEFT_EYE_CENTER_IDX, width, height)
    right_center = _face_point(face_landmarks, RIGHT_EYE_CENTER_IDX, width, height)
    if left_center is None or right_center is None:
        return None
    scale = float(np.linalg.norm(left_center - right_center))
    if scale <= 1e-6:
        return None
    return scale

