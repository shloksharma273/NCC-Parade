from __future__ import annotations

import numpy as np

# --- Geometry primitives (copied from kadam_tal/salute; self-contained) -----


def to_pixel(landmark, width: int, height: int) -> np.ndarray:
    """Convert a normalised MediaPipe landmark to pixel coordinates."""
    return np.array([landmark.x * width, landmark.y * height], dtype=float)


def angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
    """Angle (degrees) between two vectors: degrees(arccos((v1.v2)/(|v1||v2|)))."""
    norm1 = float(np.linalg.norm(v1))
    norm2 = float(np.linalg.norm(v2))
    if norm1 <= 1e-9 or norm2 <= 1e-9:
        return float("nan")
    cosine = float(np.dot(v1, v2) / (norm1 * norm2))
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def angle_at_joint(
    point_a: np.ndarray,
    point_b: np.ndarray,
    point_c: np.ndarray,
) -> float:
    """Interior angle at point_b formed by segments b->a and b->c."""
    return angle_between(np.asarray(point_a) - np.asarray(point_b),
                         np.asarray(point_c) - np.asarray(point_b))


def perpendicular_separation(point_a: np.ndarray, point_b: np.ndarray, axis: np.ndarray) -> float:
    """Distance between two points measured perpendicular to the given axis."""
    separation = np.asarray(point_b) - np.asarray(point_a)
    axis_len = float(np.linalg.norm(axis))
    if axis_len <= 1e-9:
        return float(np.linalg.norm(separation))
    axis_u = axis / axis_len
    perpendicular = separation - np.dot(separation, axis_u) * axis_u
    return float(np.linalg.norm(perpendicular))
