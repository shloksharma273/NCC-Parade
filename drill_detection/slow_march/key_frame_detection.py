from __future__ import annotations

import numpy as np

from .landmarks import SlowMarchFrameMetrics


def smooth_signal(values: np.ndarray, window: int) -> np.ndarray:
    # Copied verbatim from kadam_tal/peak_detection.py (moving-average box filter).
    if window <= 1 or len(values) == 0:
        return values.copy()
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def find_step_peaks(
    metrics: list[SlowMarchFrameMetrics],
    smooth_window: int,
    min_distance: int,
    min_prominence_deg: float | None,
    min_prominence_ratio: float,
) -> list[SlowMarchFrameMetrics]:
    """Detect step extremes = local maxima of the inter-leg-angle signal.

    Same prominence/min-distance/smoothing algorithm as
    kadam_tal.peak_detection.find_knee_peaks, but the signal is the inter-leg
    angle (deg) instead of knee-lift (px). Thighs are near-parallel at stance
    (small angle); the split widens and peaks when the raised leg reaches the
    front of the step.
    """
    if not metrics:
        return []

    angles = np.array([m.inter_leg_angle_deg for m in metrics], dtype=float)
    # NaN inter-leg angles (missing landmarks) collapse to 0 so they never win as peaks.
    angles = np.nan_to_num(angles, nan=0.0)
    smoothed = smooth_signal(angles, smooth_window)

    angle_range = float(smoothed.max() - smoothed.min())
    prominence = min_prominence_deg
    if prominence is None:
        # Derive an absolute prominence floor (deg) from the signal range; the 3.0 deg
        # floor prevents jitter from registering as steps on near-flat signals.
        prominence = max(3.0, angle_range * min_prominence_ratio)

    peak_indices = _find_local_maxima(smoothed, min_distance, prominence)
    return [metrics[i] for i in peak_indices]


def _find_local_maxima(values: np.ndarray, min_distance: int, min_prominence: float) -> list[int]:
    # Copied verbatim from kadam_tal/peak_detection.py._find_local_maxima.
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
