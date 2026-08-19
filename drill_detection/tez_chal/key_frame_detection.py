from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .landmarks import TezChalFrameMetrics

if TYPE_CHECKING:
    from .config import PipelineConfig


def smooth_signal(values: np.ndarray, window: int) -> np.ndarray:
    """Moving-average box filter (verbatim from slow_march / kadam_tal)."""
    if window <= 1 or len(values) == 0:
        return values.copy()
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def find_step_peaks(
    metrics: list[TezChalFrameMetrics], config: "PipelineConfig"
) -> list[TezChalFrameMetrics]:
    """Key frames = local MAXIMA of the inter-leg angle (legs maximally split).

    Same prominence / min-distance / smoothing machinery as
    slow_march.key_frame_detection._find_by_inter_leg_angle and
    kadam_tal.peak_detection.find_knee_peaks.
    """
    if not metrics:
        return []

    angles = np.array([m.inter_leg_angle_deg for m in metrics], dtype=float)
    angles = np.nan_to_num(angles, nan=0.0)  # missing landmarks -> 0 so they never win as peaks
    smoothed = smooth_signal(angles, config.smooth_window)

    angle_range = float(smoothed.max() - smoothed.min())
    prominence = config.min_peak_prominence_deg
    if prominence is None:
        # Absolute prominence floor (deg): 3 deg guards against jitter on a flat signal.
        prominence = max(3.0, angle_range * config.min_peak_prominence_ratio)

    peak_indices = _find_local_maxima(smoothed, config.min_peak_distance_frames, prominence)
    # Overwrite each metric's angle with the smoothed value we actually peaked on, so the
    # emitted results match what the detector saw.
    for i in peak_indices:
        metrics[i].inter_leg_angle_deg = round(float(smoothed[i]), 2)
    return [metrics[i] for i in peak_indices]


def _find_local_maxima(values: np.ndarray, min_distance: int, min_prominence: float) -> list[int]:
    """Copied verbatim from slow_march / kadam_tal._find_local_maxima."""
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
