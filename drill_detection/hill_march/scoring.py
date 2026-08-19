from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .difficulty import scaled_tolerances


# --------------------------------------------------------------------------------------
# Scoring primitives. Each returns 10 inside the perfect band, 0 beyond the fail band,
# linear in between.
#   score_by_tolerance <- kadam_tal / slow_march (error vs a target)
#   score_by_max       <- salute / baju_swing    (smaller is better; perfect_max/fail_max)
#   score_by_min       <- NEW here                (larger is better; perfect_min/fail_min)
# --------------------------------------------------------------------------------------
def score_by_tolerance(value: float, target: float, perfect_tolerance: float, fail_tolerance: float) -> float:
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


def score_by_min(value: float, perfect_min: float, fail_min: float) -> float:
    """Larger is better: 10 at/above perfect_min, 0 at/below fail_min, linear between.
    Used for parameter 1 (the inter-leg angle should be MORE than ~70 deg)."""
    if math.isnan(value):
        return 0.0
    if value >= perfect_min:
        return 10.0
    if value <= fail_min:
        return 0.0
    return 10.0 * (value - fail_min) / (perfect_min - fail_min)


# --------------------------------------------------------------------------------------
# Difficulty bands (documented module constants; NO magic numbers in the logic below).
# Each tuple = (perfect_at_easy, perfect_at_hard, fail_at_easy, fail_at_hard) fed into
# scaled_tolerances(difficulty, ...).
# --------------------------------------------------------------------------------------
# Parameter 1 — legs apart. score_by_min band = (perfect_min easy/hard, fail_min easy/hard).
# Easy requires a smaller minimum angle, hard a larger one; centred so difficulty 2 ~= 70 deg.
LEGS_APART_BAND = (60.0, 80.0, 30.0, 50.0)   # inter-leg angle >= perfect_min => full marks
# Parameter 2a — arms straight: elbow error vs 180 deg (score_by_tolerance).
ARM_STRAIGHT_BAND = (15.0, 5.0, 45.0, 20.0)
# Parameter 2b — arms close to body: shoulder abduction toward torso (score_by_max, 0 == alongside).
ARM_CLOSE_BAND = (15.0, 6.0, 55.0, 30.0)
# Parameter 3 — legs straight: knee error vs 180 deg (score_by_tolerance).
LEG_STRAIGHT_BAND = (10.0, 4.0, 35.0, 15.0)
# Parameter 4 — head straight: yaw ratio (score_by_max) + tilt error vs 0 deg (score_by_tolerance).
HEAD_YAW_BAND = (0.20, 0.06, 0.55, 0.30)
HEAD_TILT_BAND = (8.0, 3.0, 35.0, 15.0)

# Per-parameter weights for the frame total. Sum == 1.0 (four equally-weighted parameters).
PARAM_WEIGHTS = {
    "legs_apart": 0.25,
    "arms": 0.25,
    "legs_straight": 0.25,
    "head_straight": 0.25,
}


@dataclass
class FrameScore:
    total: float
    legs_apart: float
    arms: float
    legs_straight: float
    head_straight: float

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 2),
            "legs_apart": round(self.legs_apart, 2),
            "arms": round(self.arms, 2),
            "legs_straight": round(self.legs_straight, 2),
            "head_straight": round(self.head_straight, 2),
        }


def score_frame(
    *,
    inter_leg_angle_deg: float,
    left_elbow_angle_deg: float,
    right_elbow_angle_deg: float,
    left_arm_abduction_deg: float,
    right_arm_abduction_deg: float,
    left_knee_angle_deg: float,
    right_knee_angle_deg: float,
    head_yaw_ratio: float,
    head_tilt_deg: float,
    difficulty: float,
    target_arm_angle_deg: float = 180.0,
    target_knee_angle_deg: float = 180.0,
    target_head_tilt_deg: float = 0.0,
) -> FrameScore:
    """Score one key frame /10 on the four hill-march parameters, then weight-average."""

    # --- 1. Legs apart: inter-leg angle should be MORE than the target (~70 deg) ---
    apart_perfect_min, apart_fail_min = scaled_tolerances(difficulty, *LEGS_APART_BAND)
    legs_apart = score_by_min(inter_leg_angle_deg, apart_perfect_min, apart_fail_min)

    # --- 2. Arms straight AND close to body: mean of (elbow straightness, abduction) ---
    arm_perfect, arm_fail = scaled_tolerances(difficulty, *ARM_STRAIGHT_BAND)
    straight = np.mean([
        score_by_tolerance(left_elbow_angle_deg, target_arm_angle_deg, arm_perfect, arm_fail),
        score_by_tolerance(right_elbow_angle_deg, target_arm_angle_deg, arm_perfect, arm_fail),
    ])
    close_perfect, close_fail = scaled_tolerances(difficulty, *ARM_CLOSE_BAND)
    close = np.mean([
        score_by_max(left_arm_abduction_deg, close_perfect, close_fail),
        score_by_max(right_arm_abduction_deg, close_perfect, close_fail),
    ])
    arms = float(np.mean([straight, close]))

    # --- 3. Legs straight: knee angle vs 180 deg, averaged L/R ---
    knee_perfect, knee_fail = scaled_tolerances(difficulty, *LEG_STRAIGHT_BAND)
    legs_straight = float(np.mean([
        score_by_tolerance(left_knee_angle_deg, target_knee_angle_deg, knee_perfect, knee_fail),
        score_by_tolerance(right_knee_angle_deg, target_knee_angle_deg, knee_perfect, knee_fail),
    ]))

    # --- 4. Head straight: facing front (yaw) + upright (tilt), averaged ---
    yaw_perfect, yaw_fail = scaled_tolerances(difficulty, *HEAD_YAW_BAND)
    yaw_score = score_by_max(abs(head_yaw_ratio) if not math.isnan(head_yaw_ratio) else float("nan"),
                             yaw_perfect, yaw_fail)
    tilt_perfect, tilt_fail = scaled_tolerances(difficulty, *HEAD_TILT_BAND)
    tilt_score = score_by_tolerance(head_tilt_deg, target_head_tilt_deg, tilt_perfect, tilt_fail)
    head_straight = float(np.mean([yaw_score, tilt_score]))

    total = (
        legs_apart * PARAM_WEIGHTS["legs_apart"]
        + arms * PARAM_WEIGHTS["arms"]
        + legs_straight * PARAM_WEIGHTS["legs_straight"]
        + head_straight * PARAM_WEIGHTS["head_straight"]
    )

    return FrameScore(
        total=total,
        legs_apart=legs_apart,
        arms=arms,
        legs_straight=legs_straight,
        head_straight=head_straight,
    )
