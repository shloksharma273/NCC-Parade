from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drill_detection.report_metadata import ReportMetadata

# ===========================================================================
# CONFIG = SINGLE SOURCE OF TRUTH. No magic numbers anywhere in the logic;
# every tunable used by scoring/detection lives here.
# ===========================================================================

# --- Camera view (§10). The drill can be filmed side-on or front-on; the UI
#     will let the user pick. Only the KEY-FRAME SIGNAL and the SWING-SPREAD
#     parameter differ between views (see signals.py / pipeline.py); the other
#     four parameters (arms/legs/fist/thumb) are identical. -------------------
SIDE_VIEW = "side"
FRONT_VIEW = "front"
VIEWS = (SIDE_VIEW, FRONT_VIEW)

# --- Scoring weights (§6.7). Each dict must sum to 1.0. --------------------
# SIDE view: five equally-weighted parameters.
WEIGHTS: dict[str, float] = {
    "arms_straight": 0.20,
    "swing_spread": 0.20,
    "legs_straight": 0.20,
    "fist": 0.20,
    "thumb": 0.20,
}
# FRONT view (§10.4): arms_straight is DROPPED and swing spread (fist height) is
# emphasised. Only the keys present here are scored/reported for the front view.
FRONT_WEIGHTS: dict[str, float] = {
    "swing_spread": 0.40,
    "legs_straight": 0.20,
    "fist": 0.20,
    "thumb": 0.20,
}

# --- Difficulty tolerance bands (§7). Each band is
#     (perfect_at_easy, perfect_at_hard, fail_at_easy, fail_at_hard)
#     and is fed verbatim to difficulty.scaled_tolerances(difficulty, *band).
#     Lower difficulty (0) => wider/easier; higher (5) => tighter/harder.
# Angle bands are in DEGREES of error from the target angle.
ELBOW_STRAIGHT_BAND = (15.0, 5.0, 45.0, 20.0)   # elbow vs 180deg (arms straight)
INTER_ARM_BAND = (20.0, 8.0, 70.0, 35.0)        # inter-arm angle vs 180deg (swing spread)
KNEE_STRAIGHT_BAND = (10.0, 4.0, 35.0, 15.0)    # knee vs 180deg (legs straight)
# Hand-ratio bands are dimensionless (hand-scale-normalised). Smaller = better,
# so they are used as (perfect_max, fail_max) via score_by_max.
FIST_CURL_BAND = (0.55, 0.35, 1.05, 0.85)       # per-finger curl ratio
THUMB_GAP_BAND = (0.45, 0.25, 1.10, 0.85)       # thumb-tip gap ratio

# --- Front-view swing spread (§10.2): height of the higher fist above the hip,
#     normalised by shoulder width. Scored PROPORTIONALLY — 0 at hip level,
#     full at "max arm reach" = FIST_HEIGHT_FULL_BAND (easy, hard) shoulder-
#     widths above the hip. Higher difficulty demands a higher fist for full
#     marks. TUNABLE dev defaults — calibrate from real front-view results.
#     Calibrated to the reference clip (fist heights ran 2.3-3.1 sw above hip);
#     re-tune against the drill's actual "full reach" standard.
FIST_HEIGHT_FULL_BAND = (2.6, 3.2)  # full-marks fist height (easy -> hard)

# --- Front-view "fist closed" (§10.3): fingers-together spread = mean distance
#     of the four finger MIDPOINTS (PIP joints, visible face of a front-on fist)
#     from their centroid, normalised by hand scale. Smaller = fingers joined
#     => better, so used as (perfect_max, fail_max) via score_by_max.
FINGER_TOGETHER_BAND = (0.35, 0.20, 0.80, 0.55)  # midpoint-spread ratio


@dataclass
class PipelineConfig:
    input_path: Path
    output_dir: Path
    # Camera view: "side" (default, inter-arm-angle signal + 5 params) or
    # "front" (fist-height signal; drops arms_straight, swing spread = fist
    # height, fist = fingers-together). See §10.
    view: str = SIDE_VIEW
    every_k_frames: int = 1
    min_detection_confidence: float = 0.5
    save_annotated_frames: bool = True
    save_raw_frames: bool = False
    smooth_window: int = 5
    min_peak_distance_frames: int = 15
    min_peak_prominence_deg: float | None = None
    min_peak_prominence_ratio: float = 0.15
    # Absolute prominence floor for the key-frame signal, per view. Side view's
    # signal is in DEGREES (floor 5.0); front view's fist-height signal is in
    # SHOULDER-WIDTH units (floor 0.08). Used when no absolute override is set.
    min_peak_prominence_floor_side: float = 5.0
    min_peak_prominence_floor_front: float = 0.08
    # Target angles (used directly by score_by_tolerance).
    target_arm_angle_deg: float = 180.0
    target_inter_arm_angle_deg: float = 180.0
    target_knee_angle_deg: float = 180.0
    # Nominal (difficulty ~= 2) hand-ratio reference thresholds. Scoring uses
    # the difficulty-scaled FIST_CURL_BAND / THUMB_GAP_BAND above; these fields
    # document the effective thresholds at default difficulty (see MATH.md).
    fist_curl_perfect_ratio: float = 0.45
    fist_curl_fail_ratio: float = 0.90
    thumb_on_top_perfect_ratio: float = 0.35
    thumb_on_top_fail_ratio: float = 1.00
    difficulty: float = 2.0
    report_metadata: ReportMetadata | None = None
