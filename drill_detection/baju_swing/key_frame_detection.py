from __future__ import annotations

import numpy as np

from .landmarks import BajuSwingFrameMetrics


def smooth_signal(values: np.ndarray, window: int) -> np.ndarray:
    # Copied verbatim from kadam_tal/peak_detection.py (moving-average smoothing).
    if window <= 1 or len(values) == 0:
        return values.copy()
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def find_swing_peaks(
    metrics: list[BajuSwingFrameMetrics],
    signal: np.ndarray,
    smooth_window: int,
    min_distance: int,
    min_prominence_abs: float | None,
    min_prominence_ratio: float,
    min_prominence_floor: float,
) -> list[BajuSwingFrameMetrics]:
    """Key frames = local maxima of ``signal`` (§2.1, §10.1).

    View-agnostic: the caller supplies the per-frame signal (side = inter-arm
    angle in degrees, front = fist height in shoulder-width units; see
    signals.py) index-aligned with ``metrics``. Same prominence/min-distance/
    smoothing algorithm as kadam_tal.peak_detection.find_knee_peaks.

    Prominence threshold = ``min_prominence_abs`` if given, else
    ``max(min_prominence_floor, signal_range * min_prominence_ratio)`` — the
    floor keeps tiny jitter from registering as a swing and is in the signal's
    own units (degrees for side, shoulder-widths for front).
    """
    if not metrics:
        return []

    smoothed = smooth_signal(np.asarray(signal, dtype=float), smooth_window)

    signal_range = float(smoothed.max() - smoothed.min())
    prominence = min_prominence_abs
    if prominence is None:
        # prominence = max(floor, range * ratio)
        prominence = max(min_prominence_floor, signal_range * min_prominence_ratio)

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
