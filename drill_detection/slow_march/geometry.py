from __future__ import annotations

import numpy as np


def angle_at_joint(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    point_c: tuple[float, float],
) -> float:
    """Interior angle at point_b formed by segments b->a and b->c, in degrees.

    Formula: theta = degrees(arccos( (v1 . v2) / (|v1| |v2|) )),
    with v1 = a - b, v2 = c - b.
    """
    a = np.array(point_a, dtype=float)
    b = np.array(point_b, dtype=float)
    c = np.array(point_c, dtype=float)
    return angle_between(a - b, c - b)


def angle_between(v1: np.ndarray | tuple[float, float], v2: np.ndarray | tuple[float, float]) -> float:
    """Angle between two vectors, in degrees.

    Formula: degrees(arccos( (v1 . v2) / (|v1| |v2|) )).
    """
    v1 = np.asarray(v1, dtype=float)
    v2 = np.asarray(v2, dtype=float)
    norm1 = float(np.linalg.norm(v1))
    norm2 = float(np.linalg.norm(v2))
    if norm1 <= 1e-9 or norm2 <= 1e-9:
        return float("nan")
    cosine = float(np.dot(v1, v2) / (norm1 * norm2))
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def angle_to_vertical(v: np.ndarray | tuple[float, float]) -> float:
    """Angle of vector v away from the (image) vertical axis, in degrees.

    Formula: degrees(arccos( |v_y| / |v| )). 0 deg == perfectly vertical.
    Uses |v_y| so an upward or downward segment both read as vertical.
    """
    v = np.asarray(v, dtype=float)
    norm = float(np.linalg.norm(v))
    if norm <= 1e-9:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(abs(float(v[1])) / norm, -1.0, 1.0))))


def angle_to_horizontal(v: np.ndarray | tuple[float, float]) -> float:
    """Angle of vector v away from the (image) horizontal axis, in degrees.

    Formula: degrees(arcsin( |v_y| / |v| )). 0 deg == perfectly flat/horizontal.
    """
    v = np.asarray(v, dtype=float)
    norm = float(np.linalg.norm(v))
    if norm <= 1e-9:
        return float("nan")
    return float(np.degrees(np.arcsin(np.clip(abs(float(v[1])) / norm, -1.0, 1.0))))
