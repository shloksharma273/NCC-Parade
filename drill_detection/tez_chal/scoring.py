from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .difficulty import scaled_tolerances


# --------------------------------------------------------------------------------------
# Scoring primitives (copied VERBATIM so the package is self-contained):
#   score_by_tolerance  <- kadam_tal / slow_march scoring.py
#   score_by_max        <- salute geometry.py / baju_swing scoring.py
# Both return 10 inside the perfect band, 0 beyond the fail band, linear in between.
# --------------------------------------------------------------------------------------
def score_by_tolerance(
    value: float,
    target: float,
    perfect_tolerance: float,
    fail_tolerance: float,
) -> float:
    if math.isnan(value):
        return 0.0
    error = abs(value - target)
    if error <= perfect_tolerance:
        return 10.0
    if error >= fail_tolerance:
        return 0.0
    return 10.0 * (1.0 - (error - perfect_tolerance) / (fail_tolerance - perfect_tolerance))


def score_by_max(value: float, perfect_max: float, fail_max: float) -> float:
    if math.isnan(value):
        return 0.0
    if value <= perfect_max:
        return 10.0
    if value >= fail_max:
        return 0.0
    return 10.0 * (1.0 - (value - perfect_max) / (fail_max - perfect_max))


# --------------------------------------------------------------------------------------
# Difficulty bands (documented module constants; NO magic numbers in the logic below).
# Each tuple = (perfect_at_easy, perfect_at_hard, fail_at_easy, fail_at_hard) fed into
# scaled_tolerances(difficulty, ...). Easy => wider/lenient, hard => tighter/strict.
# Angle bands are DEGREES of error from the target (180 == straight).
# --------------------------------------------------------------------------------------
ARM_STRAIGHT_BAND = (15.0, 5.0, 45.0, 20.0)   # elbow angle error vs 180 deg (same as baju ELBOW band)
LEG_STRAIGHT_BAND = (10.0, 4.0, 35.0, 15.0)   # knee angle error vs 180 deg (same as baju KNEE band)
# Fist curl ratio is dimensionless (hand-scale normalised); smaller == more closed,
# so it is scored with score_by_max as (perfect_max, fail_max). Same as baju FIST_CURL_BAND.
FIST_CURL_BAND = (0.55, 0.35, 1.05, 0.85)

# Per-parameter weights for the frame total. Sum == 1.0. All three ideals are held
# "always", so they contribute equally.
PARAM_WEIGHTS = {
    "arms_straight": 1.0 / 3.0,
    "legs_straight": 1.0 / 3.0,
    "fist_closed": 1.0 / 3.0,
}


@dataclass
class FrameScore:
    total: float
    arms_straight: float
    legs_straight: float
    fist_closed: float
    hands_detected: int  # 0/1/2 — how many hands the IMAGE-mode pass found this frame

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 2),
            "arms_straight": round(self.arms_straight, 2),
            "legs_straight": round(self.legs_straight, 2),
            "fist_closed": round(self.fist_closed, 2),
            "hands_detected": self.hands_detected,
        }


def score_frame(
    *,
    left_elbow_angle_deg: float,
    right_elbow_angle_deg: float,
    left_knee_angle_deg: float,
    right_knee_angle_deg: float,
    fist_closed_score: float,
    hands_detected: int,
    difficulty: float,
    target_arm_angle_deg: float = 180.0,
    target_knee_angle_deg: float = 180.0,
) -> FrameScore:
    """Score one key frame /10 on the three tez-chal parameters, then weight-average.

    Each parameter is graded by how far the pose deviates from its ideal:
      * arms_straight -> both elbows at 180 deg   (score_by_tolerance)
      * legs_straight -> both knees  at 180 deg   (score_by_tolerance)
      * fist_closed   -> fingers curled to wrist  (already a /10 from hand_analysis)
    """
    # --- Arms straight: elbow angle vs 180 deg, averaged L/R ---
    arm_perfect, arm_fail = scaled_tolerances(difficulty, *ARM_STRAIGHT_BAND)
    left_arm = score_by_tolerance(left_elbow_angle_deg, target_arm_angle_deg, arm_perfect, arm_fail)
    right_arm = score_by_tolerance(right_elbow_angle_deg, target_arm_angle_deg, arm_perfect, arm_fail)
    arms_straight = float(np.mean([left_arm, right_arm]))

    # --- Legs straight: knee angle vs 180 deg, averaged L/R ---
    knee_perfect, knee_fail = scaled_tolerances(difficulty, *LEG_STRAIGHT_BAND)
    left_leg = score_by_tolerance(left_knee_angle_deg, target_knee_angle_deg, knee_perfect, knee_fail)
    right_leg = score_by_tolerance(right_knee_angle_deg, target_knee_angle_deg, knee_perfect, knee_fail)
    legs_straight = float(np.mean([left_leg, right_leg]))

    # --- Fist closed: computed upstream from hand landmarks (0 when no hand found) ---
    fist_closed = fist_closed_score

    total = (
        arms_straight * PARAM_WEIGHTS["arms_straight"]
        + legs_straight * PARAM_WEIGHTS["legs_straight"]
        + fist_closed * PARAM_WEIGHTS["fist_closed"]
    )

    return FrameScore(
        total=total,
        arms_straight=arms_straight,
        legs_straight=legs_straight,
        fist_closed=fist_closed,
        hands_detected=hands_detected,
    )
