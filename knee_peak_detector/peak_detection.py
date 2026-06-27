from __future__ import annotations

import numpy as np

from .landmarks import PeakFrameMetrics


def smooth_signal(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or len(values) == 0:
        return values.copy()
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def find_knee_peaks(
    metrics: list[PeakFrameMetrics],
    smooth_window: int,
    min_distance: int,
    min_prominence_px: float | None,
    min_prominence_ratio: float,
) -> list[PeakFrameMetrics]:
    if not metrics:
        return []

    lifts = np.array([m.peak_knee_lift_px for m in metrics], dtype=float)
    smoothed = smooth_signal(lifts, smooth_window)

    lift_range = float(smoothed.max() - smoothed.min())
    prominence = min_prominence_px
    if prominence is None:
        prominence = max(15.0, lift_range * min_prominence_ratio)

    peak_indices = _find_local_maxima(smoothed, min_distance, prominence)
    return [metrics[i] for i in peak_indices]


def _find_local_maxima(values: np.ndarray, min_distance: int, min_prominence: float) -> list[int]:
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
