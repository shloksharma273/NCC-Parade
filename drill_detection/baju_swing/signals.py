from __future__ import annotations

import numpy as np

from .config import FRONT_VIEW, SIDE_VIEW
from .landmarks import BajuSwingFrameMetrics

# ===========================================================================
# Key-frame signal (§10.1). The peak-detection algorithm in
# key_frame_detection.py is view-agnostic; it operates on whatever 1-D signal
# this module hands it. Only the signal (and its prominence floor) changes
# between views.
#   - SIDE view:  inter-arm angle in degrees (a swing extreme => local MAX).
#   - FRONT view: fist height of the higher hand, normalised by shoulder width
#                 (the topmost fist of the swing cycle => local MAX).
# ===========================================================================


def build_key_frame_signal(metrics: list[BajuSwingFrameMetrics], view: str) -> np.ndarray:
    """Return the 1-D signal whose local maxima are the swing key frames.

    The array is index-aligned with ``metrics`` (one value per valid frame), so
    the peak indices map straight back to the frame metrics.
    """
    if view == FRONT_VIEW:
        return _fist_height_signal(metrics)
    if view == SIDE_VIEW:
        # Inter-arm angle; NaN (missing landmarks) cannot be a swing extreme.
        signal = np.array([m.inter_arm_angle_deg for m in metrics], dtype=float)
        return np.nan_to_num(signal, nan=0.0)
    raise ValueError(f"Unknown view: {view!r} (expected {SIDE_VIEW!r} or {FRONT_VIEW!r})")


def _fist_height_signal(metrics: list[BajuSwingFrameMetrics]) -> np.ndarray:
    """FRONT-view signal: height of the HIGHER fist above the hip line, in
    shoulder-width units (§10.1).

    This is exactly ``BajuSwingFrameMetrics.fist_height_norm`` (computed once in
    landmarks.py): image y grows downward, so height-above-hip makes the topmost
    fist a local MAXIMUM (matching the side-view convention), normalised by
    shoulder width for a scale-invariant prominence threshold. Per §10 it is the
    max over the two hands ("higher of the two fists")."""
    return np.array([m.fist_height_norm for m in metrics], dtype=float)
