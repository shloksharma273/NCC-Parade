from __future__ import annotations

import numpy as np


def to_pixel(landmark, width: int, height: int) -> np.ndarray:
    return np.array([landmark.x * width, landmark.y * height], dtype=float)


def angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
    norm1 = float(np.linalg.norm(v1))
    norm2 = float(np.linalg.norm(v2))
    if norm1 <= 1e-9 or norm2 <= 1e-9:
        return float("nan")
    cosine = float(np.dot(v1, v2) / (norm1 * norm2))
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def angle_at_joint(point_a: np.ndarray, point_b: np.ndarray, point_c: np.ndarray) -> float:
    return angle_between(point_a - point_b, point_c - point_b)


def score_by_tolerance(
    value: float,
    target: float,
    perfect_tolerance: float,
    fail_tolerance: float,
) -> float:
    if np.isnan(value):
        return 0.0
    error = abs(value - target)
    if error <= perfect_tolerance:
        return 10.0
    if error >= fail_tolerance:
        return 0.0
    return 10.0 * (1.0 - (error - perfect_tolerance) / (fail_tolerance - perfect_tolerance))


def score_by_max(value: float, perfect_max: float, fail_max: float) -> float:
    if np.isnan(value):
        return 0.0
    if value <= perfect_max:
        return 10.0
    if value >= fail_max:
        return 0.0
    return 10.0 * (1.0 - (value - perfect_max) / (fail_max - perfect_max))


def perpendicular_separation(point_a: np.ndarray, point_b: np.ndarray, axis: np.ndarray) -> float:
    """Distance between two points measured perpendicular to the given axis."""
    separation = point_b - point_a
    axis_len = float(np.linalg.norm(axis))
    if axis_len <= 1e-9:
        return float(np.linalg.norm(separation))
    axis_u = axis / axis_len
    perpendicular = separation - np.dot(separation, axis_u) * axis_u
    return float(np.linalg.norm(perpendicular))
