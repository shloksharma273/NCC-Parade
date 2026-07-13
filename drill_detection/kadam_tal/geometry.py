from __future__ import annotations

import numpy as np


def angle_at_joint(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    point_c: tuple[float, float],
) -> float:
    """Return the interior angle at point_b formed by segments point_a-point_b and point_c-point_b."""
    a = np.array(point_a, dtype=float)
    b = np.array(point_b, dtype=float)
    c = np.array(point_c, dtype=float)

    v1 = a - b
    v2 = c - b
    norm1 = float(np.linalg.norm(v1))
    norm2 = float(np.linalg.norm(v2))
    if norm1 <= 1e-9 or norm2 <= 1e-9:
        return float("nan")

    cosine = float(np.dot(v1, v2) / (norm1 * norm2))
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
