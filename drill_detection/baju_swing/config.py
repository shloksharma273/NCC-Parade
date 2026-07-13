from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drill_detection.report_metadata import ReportMetadata

# ===========================================================================
# CONFIG = SINGLE SOURCE OF TRUTH. No magic numbers anywhere in the logic;
# every tunable used by scoring/detection lives here.
# ===========================================================================

# --- Scoring weights (§6.7). Must sum to 1.0. -----------------------------
WEIGHTS: dict[str, float] = {
    "arms_straight": 0.20,
    "swing_spread": 0.20,
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


@dataclass
class PipelineConfig:
    input_path: Path
    output_dir: Path
    every_k_frames: int = 1
    min_detection_confidence: float = 0.5
    save_annotated_frames: bool = True
    save_raw_frames: bool = False
    smooth_window: int = 5
    min_peak_distance_frames: int = 15
    min_peak_prominence_deg: float | None = None
    min_peak_prominence_ratio: float = 0.15
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
