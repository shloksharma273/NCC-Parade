from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .geometry import angle_between, angle_to_horizontal
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

    The ACTIVE side-view detector is "foot_passing": the once-per-pace "passing" instant where
    BOTH feet are parallel to the ground (hind grounded flat + front held flat) and the legs
    are close together, found as self-calibrating local minima of a combined cost (see
    _find_by_foot_passing). The stride-based detectors below share a common peak->snap->gate->
    dedupe machinery (see _select_steps), differing only in their snap cost + accept gate:

      - "foot_passing" (ACTIVE, side): both feet flat + legs together; no hardcoded angles.
      - "stride" (SAVED): stride peaks snapped to the most STATIC grounded-foot frame.
      - "perpendicular_hind": stride peaks snapped to the most PERPENDICULAR hind leg; rejects
        steps not within config.hind_perpendicular_max_deg of vertical.
      - "merged": snap on a blend of static + perpendicular and accept only if BOTH pass.
      - "inter_leg_angle" (front-view fallback): the legacy thigh-vector angle maxima.

    Selection comes from config.key_frame_signal
    ("auto"/"foot_passing"/"stride"/"perpendicular_hind"/"merged"/"inter_leg_angle").
    """
    if not metrics:
        return []

    signal = config.key_frame_signal
    if signal == "auto":
        # Side view => ACTIVE foot-passing detector (both feet flat + legs together). Front view
        # keeps the legacy inter-leg-angle detector. Change this one line to swap the active
        # pipeline for every caller that leaves key_frame_signal on "auto".
        signal = "foot_passing" if config.view == "side" else "inter_leg_angle"

    if signal == "inter_leg_angle":
        return _find_by_inter_leg_angle(metrics, config)
    if signal == "stride":
        return _find_by_stride(metrics, config)                 # SAVED pipeline
    if signal == "merged":
        return _find_by_stride_perpendicular(metrics, config)   # combined static + perpendicular
    if signal == "perpendicular_hind":
        return _find_by_perpendicular_hind(metrics, config)     # stride peak + plumb hind leg
    return _find_by_foot_passing(metrics, config)               # ACTIVE pipeline (side default)


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


def _grounded_vertical_signal(metrics: list[SlowMarchFrameMetrics]) -> np.ndarray:
    # Hind leg perpendicular => off-vertical angle (deg) of the GROUNDED leg; 0 == plumb.
    # This is the quantity the real-world key frame is anchored on (see _find_by_perpendicular_hind).
    return np.array([float(m.grounded_vertical_deg) for m in metrics], dtype=float)


def _select_steps(
    metrics: list[SlowMarchFrameMetrics],
    config: "PipelineConfig",
    *,
    separation: np.ndarray,
    separation_s: np.ndarray,
    snap_cost: np.ndarray,
    is_accepted,
) -> list[int]:
    """Shared peak -> snap -> gate -> dedupe machinery for every stride-based detector.

    The detectors differ ONLY in two injected pieces:
      * snap_cost[j]   : per-frame cost minimised inside the snap window. "stride" uses
                         grounded-foot speed (most static), "perpendicular_hind" uses the
                         off-vertical angle (most plumb), "merged" uses a blend of both.
      * is_accepted(j) : the MANDATORY gate deciding whether a snapped frame is a real step.
    Everything else (stride peak finding, the near-farthest snap window, the min-stride gate,
    the never-return-zero fallback, and dedupe) is identical here — which is exactly what
    makes the current, new, and merged pipelines mergeable.
    """
    signal_range = float(separation_s.max() - separation_s.min())
    # Ratio-based prominence (fraction of signal range) — unit-agnostic for the normalised stride.
    prominence = max(1e-6, signal_range * config.stride_min_prominence_ratio)
    raw_peaks = _find_local_maxima(separation_s, config.min_peak_distance_frames, prominence)

    window = config.hind_static_snap_window
    tol = config.hind_static_snap_separation_tol

    def snap(peak: int) -> int:
        # Within +/- window of the raw separation peak, keep frames where the front leg is
        # still near-farthest (separation >= (1 - tol) * peak) and pick the one that minimises
        # snap_cost -> "front farthest AND hind planted" (planted per the chosen detector).
        lo, hi = max(0, peak - window), min(len(metrics), peak + window + 1)
        threshold = separation_s[peak] * (1.0 - tol)
        candidates = [j for j in range(lo, hi) if separation_s[j] >= threshold] or [peak]
        return min(candidates, key=lambda j: snap_cost[j])

    # A real step extreme needs the front leg genuinely far forward: require stride >= a
    # fraction of the clip's max stride. This rejects small local bumps in the signal.
    min_stride = float(separation.max()) * config.min_stride_ratio_of_max

    # Snap each raw peak; keep only those where the front leg is far forward AND the hind leg
    # passes the detector's mandatory gate.
    accepted: list[int] = []
    fallback: list[int] = []
    for peak in raw_peaks:
        snapped = snap(peak)
        if separation[snapped] < min_stride:  # front leg not far enough forward -> not a step
            continue
        fallback.append(snapped)
        if is_accepted(snapped):
            accepted.append(snapped)

    # Guard: if the mandatory gate rejects everything on an otherwise-valid clip, fall back to
    # the snapped separation peaks so we still return sensible key frames (never silently 0).
    chosen = accepted if accepted else fallback
    return _dedupe_by_distance(chosen, separation, config.min_peak_distance_frames)


def _emit(
    metrics: list[SlowMarchFrameMetrics],
    selected: list[int],
    separation: np.ndarray,
    grounded_speed_s: np.ndarray,
) -> list[SlowMarchFrameMetrics]:
    # Attach the key-frame diagnostics for the selected frames and return them in order.
    result: list[SlowMarchFrameMetrics] = []
    for idx in selected:
        m = metrics[idx]
        m.stride_separation_norm = round(float(separation[idx]), 4)
        m.hind_foot_speed_norm = round(float(grounded_speed_s[idx]), 4)
        result.append(m)
    return result


def _find_by_stride(metrics: list[SlowMarchFrameMetrics], config: "PipelineConfig") -> list[SlowMarchFrameMetrics]:
    """SAVED current pipeline: front leg farthest + hind foot MOST STATIC (speed-based).

    Behaviour is preserved verbatim; kept selectable via key_frame_signal="stride" so we can
    A/B against the new perpendicular detector and merge the two later.
    """
    separation = _stride_separation(metrics)
    separation_s = smooth_signal(separation, config.smooth_window)
    # Light smoothing on the foot-speed so a single noisy frame doesn't hide a planted foot.
    grounded_speed_s = smooth_signal(_grounded_foot_speed(metrics), min(config.smooth_window, 3))

    selected = _select_steps(
        metrics,
        config,
        separation=separation,
        separation_s=separation_s,
        snap_cost=grounded_speed_s,  # snap to the MOST STATIC hind foot
        is_accepted=lambda j: grounded_speed_s[j] <= config.hind_static_max_speed_ratio,
    )
    return _emit(metrics, selected, separation, grounded_speed_s)


def _find_by_perpendicular_hind(
    metrics: list[SlowMarchFrameMetrics], config: "PipelineConfig"
) -> list[SlowMarchFrameMetrics]:
    """NEW active pipeline (real-world definition): front leg farthest + HIND LEG PERPENDICULAR.

    The hind (grounded) leg being perpendicular to the ground is MANDATORY. Each stride peak
    (front leg farthest = middle of the step) is snapped to the nearby frame where the grounded
    leg is most plumb (min off-vertical angle), and any step whose hind leg never comes within
    config.hind_perpendicular_max_deg of vertical is rejected.
    """
    separation = _stride_separation(metrics)
    separation_s = smooth_signal(separation, config.smooth_window)
    # Light smoothing so a single noisy frame doesn't hide the plumb instant.
    vertical_s = smooth_signal(_grounded_vertical_signal(metrics), min(config.smooth_window, 3))
    grounded_speed_s = smooth_signal(_grounded_foot_speed(metrics), min(config.smooth_window, 3))

    selected = _select_steps(
        metrics,
        config,
        separation=separation,
        separation_s=separation_s,
        snap_cost=vertical_s,  # snap to the MOST PERPENDICULAR hind leg (min off-vertical angle)
        is_accepted=lambda j: vertical_s[j] <= config.hind_perpendicular_max_deg,  # MUST: hind plumb
    )
    return _emit(metrics, selected, separation, grounded_speed_s)


def _find_by_stride_perpendicular(
    metrics: list[SlowMarchFrameMetrics], config: "PipelineConfig"
) -> list[SlowMarchFrameMetrics]:
    """FUTURE merged pipeline (ready, not default): front farthest + hind BOTH static AND plumb.

    Snap cost = normalised(grounded-foot speed) blended with normalised(off-vertical angle);
    a step is accepted only if the snapped frame is BOTH static (speed gate) AND perpendicular
    (vertical gate). Enable with key_frame_signal="merged" / --key-frame-signal merged.
    """
    separation = _stride_separation(metrics)
    separation_s = smooth_signal(separation, config.smooth_window)
    speed_s = smooth_signal(_grounded_foot_speed(metrics), min(config.smooth_window, 3))
    vertical_s = smooth_signal(_grounded_vertical_signal(metrics), min(config.smooth_window, 3))

    # Normalise each term to [0, 1] over the clip so the weights are comparable across units
    # (speed is body-lengths/frame; vertical is degrees).
    def _norm(a: np.ndarray) -> np.ndarray:
        rng = float(a.max() - a.min())
        return (a - a.min()) / rng if rng > 1e-9 else np.zeros_like(a)

    snap_cost = (
        config.merged_speed_weight * _norm(speed_s)
        + config.merged_perpendicular_weight * _norm(vertical_s)
    )

    selected = _select_steps(
        metrics,
        config,
        separation=separation,
        separation_s=separation_s,
        snap_cost=snap_cost,  # snap to the frame that is jointly most static AND most plumb
        is_accepted=lambda j: (
            speed_s[j] <= config.hind_static_max_speed_ratio
            and vertical_s[j] <= config.hind_perpendicular_max_deg
        ),
    )
    return _emit(metrics, selected, separation, speed_s)


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
# ACTIVE detector: foot-passing (both feet parallel to ground + legs together)
# --------------------------------------------------------------------------------------

def _sole_flatness(heel_px: tuple[float, float], toe_px: tuple[float, float]) -> float:
    # Angle of the foot SOLE (heel->toe) to the horizontal; 0 == foot flat / parallel to ground.
    return angle_to_horizontal((toe_px[0] - heel_px[0], toe_px[1] - heel_px[1]))


def _inter_leg_split(m: SlowMarchFrameMetrics) -> float:
    # Angle between the two hip->ankle leg vectors; small == legs (feet) close together.
    left = (m.left_ankle_px[0] - m.left_hip_px[0], m.left_ankle_px[1] - m.left_hip_px[1])
    right = (m.right_ankle_px[0] - m.right_hip_px[0], m.right_ankle_px[1] - m.right_hip_px[1])
    return angle_between(left, right)


def _robust_norm(values: np.ndarray, low_pct: float, high_pct: float) -> np.ndarray:
    # Normalise to [0, 1] over the clip's own [low_pct, high_pct] percentile range. This is what
    # makes the detector SELF-CALIBRATING: thresholds come from each clip, not hardcoded degrees,
    # so a taller/closer/farther cadet or a faster pace all still work.
    arr = np.nan_to_num(values.astype(float), nan=float(np.nanmax(values)) if np.isfinite(np.nanmax(values)) else 0.0)
    lo, hi = float(np.percentile(arr, low_pct)), float(np.percentile(arr, high_pct))
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def _find_by_foot_passing(
    metrics: list[SlowMarchFrameMetrics], config: "PipelineConfig"
) -> list[SlowMarchFrameMetrics]:
    """ACTIVE side-view detector: the "passing" instant of each pace.

    A slow-march key frame is where BOTH feet are parallel to the ground (hind grounded flat +
    front held flat) AND the legs are close together. During a real stride at least one foot is
    heel/toe-up, so this pose is unique to the once-per-pace passing instant. Key frames are the
    local minima of a combined, self-calibrating cost:

        cost = w_hind * norm(hind_flat) + w_front * norm(front_flat) + w_split * norm(split)

    where each signal is normalised to the clip's own percentile range (no hardcoded angles).
    """
    hind_flat = np.empty(len(metrics), dtype=float)
    front_flat = np.empty(len(metrics), dtype=float)
    split = np.empty(len(metrics), dtype=float)
    for i, m in enumerate(metrics):
        # grounded = hind (planted) leg, raised = front (driven) leg — assigned upstream by
        # horizontal foot position for side view (see landmarks.assign_leg_roles_by_position).
        if m.grounded_leg == "left":
            hind_flat[i] = _sole_flatness(m.left_heel_px, m.left_foot_px)
            front_flat[i] = _sole_flatness(m.right_heel_px, m.right_foot_px)
        else:
            hind_flat[i] = _sole_flatness(m.right_heel_px, m.right_foot_px)
            front_flat[i] = _sole_flatness(m.left_heel_px, m.left_foot_px)
        split[i] = _inter_leg_split(m)

    w = min(config.smooth_window, 3)
    hind_flat_s = smooth_signal(hind_flat, w)
    front_flat_s = smooth_signal(front_flat, w)
    split_s = smooth_signal(split, w)

    cost = (
        config.foot_passing_hind_flat_weight * _robust_norm(hind_flat_s, config.foot_passing_norm_low_pct, config.foot_passing_norm_high_pct)
        + config.foot_passing_front_flat_weight * _robust_norm(front_flat_s, config.foot_passing_norm_low_pct, config.foot_passing_norm_high_pct)
        + config.foot_passing_split_weight * _robust_norm(split_s, config.foot_passing_norm_low_pct, config.foot_passing_norm_high_pct)
    )
    cost_s = smooth_signal(cost, w)

    # Key frames = local MINIMA of the cost == local maxima of its negative. Prominence as a
    # fraction of the cost range rejects shallow dips so we get ~one clean passing instant/pace.
    cost_range = float(cost_s.max() - cost_s.min())
    prominence = max(1e-6, cost_range * config.foot_passing_min_prominence_ratio)
    selected = _find_local_maxima(-cost_s, config.min_peak_distance_frames, prominence)

    result: list[SlowMarchFrameMetrics] = []
    for idx in selected:
        m = metrics[idx]
        m.hind_foot_flat_deg = round(float(hind_flat_s[idx]), 2)
        m.front_foot_flat_deg = round(float(front_flat_s[idx]), 2)
        m.inter_leg_split_deg = round(float(split_s[idx]), 2)
        result.append(m)
    return result


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
