from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .landmarks import SlowMarchFrameMetrics

if TYPE_CHECKING:
    from .config import PipelineConfig


def smooth_signal(values: np.ndarray, window: int) -> np.ndarray:
    # Copied verbatim from kadam_tal/peak_detection.py (moving-average box filter).
    if window <= 1 or len(values) == 0:
        return values.copy()
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def find_step_peaks(metrics: list[SlowMarchFrameMetrics], config: "PipelineConfig") -> list[SlowMarchFrameMetrics]:
    """Detect slow-march step key frames.

    A correct slow-march key frame is the instant the FRONT leg is farthest forward
    AND the HIND (grounded) leg is planted/static. Two detectors are available:

      - "stride" (side view, default): local maxima of the normalised horizontal ankle
        separation (front leg farthest), each snapped to the nearby frame where the
        grounded foot is most static (hind leg planted), rejecting peaks where the
        planted foot is still moving (mid-transition, not a settled step extreme).
      - "inter_leg_angle" (front-view fallback): the legacy thigh-vector angle maxima.

    Selection ("auto"/"stride"/"inter_leg_angle") comes from config.key_frame_signal.
    """
    if not metrics:
        return []

    signal = config.key_frame_signal
    if signal == "auto":
        signal = "stride" if config.view == "side" else "inter_leg_angle"

    if signal == "inter_leg_angle":
        return _find_by_inter_leg_angle(metrics, config)
    return _find_by_stride(metrics, config)


# --------------------------------------------------------------------------------------
# Stride detector: front leg farthest + hind leg static
# --------------------------------------------------------------------------------------

def _body_scale(m: SlowMarchFrameMetrics) -> float:
    # Body scale = mean hip->ankle leg length (px), clamped >= 1. Normalises stride and
    # foot-speed so thresholds are invariant to camera distance / person size.
    left_len = float(np.hypot(m.left_ankle_px[0] - m.left_hip_px[0], m.left_ankle_px[1] - m.left_hip_px[1]))
    right_len = float(np.hypot(m.right_ankle_px[0] - m.right_hip_px[0], m.right_ankle_px[1] - m.right_hip_px[1]))
    return max(1.0, (left_len + right_len) / 2.0)


def _stride_separation(metrics: list[SlowMarchFrameMetrics]) -> np.ndarray:
    # Front leg farthest => horizontal (x) distance between the two ankles, body-scale
    # normalised: stride[i] = |left_ankle_x - right_ankle_x| / body_scale.
    out = np.zeros(len(metrics), dtype=float)
    for i, m in enumerate(metrics):
        out[i] = abs(m.left_ankle_px[0] - m.right_ankle_px[0]) / _body_scale(m)
    return out


def _grounded_foot_speed(metrics: list[SlowMarchFrameMetrics]) -> np.ndarray:
    # Hind leg static => per-frame horizontal speed of the GROUNDED ankle, body-scale
    # normalised. Each ankle's own displacement is used (robust to the grounded/raised
    # label flipping between frames); speed[i] picks whichever ankle is grounded at i.
    n = len(metrics)
    speed = np.zeros(n, dtype=float)
    for i in range(1, n):
        bs = _body_scale(metrics[i])
        left_disp = abs(metrics[i].left_ankle_px[0] - metrics[i - 1].left_ankle_px[0]) / bs
        right_disp = abs(metrics[i].right_ankle_px[0] - metrics[i - 1].right_ankle_px[0]) / bs
        speed[i] = left_disp if metrics[i].grounded_leg == "left" else right_disp
    return speed


def _find_by_stride(metrics: list[SlowMarchFrameMetrics], config: "PipelineConfig") -> list[SlowMarchFrameMetrics]:
    separation = _stride_separation(metrics)
    separation_s = smooth_signal(separation, config.smooth_window)
    # Light smoothing on the foot-speed so a single noisy frame doesn't hide a planted foot.
    grounded_speed_s = smooth_signal(_grounded_foot_speed(metrics), min(config.smooth_window, 3))

    signal_range = float(separation_s.max() - separation_s.min())
    # Ratio-based prominence (fraction of signal range) — unit-agnostic for the normalised stride.
    prominence = max(1e-6, signal_range * config.stride_min_prominence_ratio)
    raw_peaks = _find_local_maxima(separation_s, config.min_peak_distance_frames, prominence)

    window = config.hind_static_snap_window
    tol = config.hind_static_snap_separation_tol

    def snap(peak: int) -> int:
        # Within +/- window of the raw separation peak, keep frames where the front leg is
        # still near-farthest (separation >= (1 - tol) * peak) and pick the one where the
        # hind (grounded) foot is most static -> "front farthest AND hind planted".
        lo, hi = max(0, peak - window), min(len(metrics), peak + window + 1)
        threshold = separation_s[peak] * (1.0 - tol)
        candidates = [j for j in range(lo, hi) if separation_s[j] >= threshold] or [peak]
        return min(candidates, key=lambda j: grounded_speed_s[j])

    # A real step extreme needs the front leg genuinely far forward: require stride >= a
    # fraction of the clip's max stride. This rejects small local bumps in the signal.
    min_stride = float(separation.max()) * config.min_stride_ratio_of_max

    # Snap each raw peak; keep only those where the front leg is far forward AND the hind
    # foot is genuinely planted.
    accepted: list[int] = []
    fallback: list[int] = []
    for peak in raw_peaks:
        snapped = snap(peak)
        if separation[snapped] < min_stride:  # front leg not far enough forward -> not a step
            continue
        fallback.append(snapped)
        if grounded_speed_s[snapped] <= config.hind_static_max_speed_ratio:
            accepted.append(snapped)

    # Guard: if the static gate rejects everything on an otherwise-valid clip, fall back to
    # the snapped separation peaks so we still return sensible key frames (never silently 0).
    chosen = accepted if accepted else fallback

    selected = _dedupe_by_distance(chosen, separation, config.min_peak_distance_frames)

    result: list[SlowMarchFrameMetrics] = []
    for idx in selected:
        m = metrics[idx]
        m.stride_separation_norm = round(float(separation[idx]), 4)
        m.hind_foot_speed_norm = round(float(grounded_speed_s[idx]), 4)
        result.append(m)
    return result


def _dedupe_by_distance(indices: list[int], separation: np.ndarray, min_distance: int) -> list[int]:
    # Snapping can push two peaks within min_distance; keep the one with the larger stride
    # separation (the clearer step extreme).
    kept: list[int] = []
    for idx in sorted(set(indices)):
        if kept and (idx - kept[-1]) < min_distance:
            if separation[idx] > separation[kept[-1]]:
                kept[-1] = idx
            continue
        kept.append(idx)
    return kept


# --------------------------------------------------------------------------------------
# Legacy inter-leg-angle detector (front-view fallback) — unchanged algorithm
# --------------------------------------------------------------------------------------

def _find_by_inter_leg_angle(
    metrics: list[SlowMarchFrameMetrics], config: "PipelineConfig"
) -> list[SlowMarchFrameMetrics]:
    """Local maxima of the inter-leg (thigh-vector) angle. Same prominence/min-distance/
    smoothing machinery as kadam_tal.peak_detection.find_knee_peaks."""
    angles = np.array([m.inter_leg_angle_deg for m in metrics], dtype=float)
    angles = np.nan_to_num(angles, nan=0.0)  # missing landmarks -> 0 so they never win as peaks
    smoothed = smooth_signal(angles, config.smooth_window)

    angle_range = float(smoothed.max() - smoothed.min())
    prominence = config.min_peak_prominence_deg
    if prominence is None:
        # Absolute prominence floor (deg): 3 deg minimum guards against jitter on flat signals.
        prominence = max(3.0, angle_range * config.min_peak_prominence_ratio)

    peak_indices = _find_local_maxima(smoothed, config.min_peak_distance_frames, prominence)
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
