from __future__ import annotations

import numpy as np

from .landmarks import BajuSwingFrameMetrics

# Minimum prominence floor (degrees) when auto-deriving prominence from the
# signal range, so tiny jitter is never treated as a real swing extreme.
MIN_PROMINENCE_FLOOR_DEG = 5.0


def smooth_signal(values: np.ndarray, window: int) -> np.ndarray:
    # Copied verbatim from kadam_tal/peak_detection.py (moving-average smoothing).
    if window <= 1 or len(values) == 0:
        return values.copy()
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def find_swing_peaks(
    metrics: list[BajuSwingFrameMetrics],
    smooth_window: int,
    min_distance: int,
    min_prominence_deg: float | None,
    min_prominence_ratio: float,
) -> list[BajuSwingFrameMetrics]:
    """Key frames = local maxima of the inter-arm-angle signal (§2.1, §6.1).

    Same prominence/min-distance/smoothing algorithm as
    kadam_tal.peak_detection.find_knee_peaks, with the signal switched from
    knee-lift pixels to inter-arm angle in degrees.
    """
    if not metrics:
        return []

    signal = np.array([m.inter_arm_angle_deg for m in metrics], dtype=float)
    # NaN inter-arm angle (missing landmarks) cannot be a swing extreme.
    signal = np.nan_to_num(signal, nan=0.0)
    smoothed = smooth_signal(signal, smooth_window)

    angle_range = float(smoothed.max() - smoothed.min())
    prominence = min_prominence_deg
    if prominence is None:
        # prominence = max(floor, range * ratio)
        prominence = max(MIN_PROMINENCE_FLOOR_DEG, angle_range * min_prominence_ratio)

    peak_indices = _find_local_maxima(smoothed, min_distance, prominence)
    return [metrics[i] for i in peak_indices]


def _find_local_maxima(values: np.ndarray, min_distance: int, min_prominence: float) -> list[int]:
    # Copied verbatim from kadam_tal/peak_detection.py::_find_local_maxima.
    peaks: list[int] = []
    n = len(values)

    for i in range(1, n - 1):
        if values[i] <= values[i - 1] or values[i] <= values[i + 1]:
            continue

        left_min = float(values[i])
        for j in range(i - 1, max(i - min_distance, -1), -1):
            left_min = min(left_min, float(values[j]))

        right_min = float(values[i])
        for j in range(i + 1, min(i + min_distance, n)):
            right_min = min(right_min, float(values[j]))

        prominence = float(values[i]) - max(left_min, right_min)
        if prominence < min_prominence:
            continue

        if peaks and (i - peaks[-1]) < min_distance:
            if values[i] > values[peaks[-1]]:
                peaks[-1] = i
        else:
            peaks.append(i)

    return peaks
