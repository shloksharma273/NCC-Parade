from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import config as cfg
from .difficulty import scaled_tolerances

# ===========================================================================
# Scoring primitives -- COPIED VERBATIM from kadam_tal/scoring.py and
# salute/geometry.py (PRD §6.8). The package does not import them at runtime.
# ===========================================================================


def score_by_tolerance(
    value: float,
    target: float,
    perfect_tolerance: float,
    fail_tolerance: float,
) -> float:
    # error = |value - target|; 10 within perfect_tolerance, 0 beyond fail_tolerance,
    # linear ramp in between: 10 * (1 - (error - perfect)/(fail - perfect)).
    if math.isnan(value):
        return 0.0

    error = abs(value - target)
    if error <= perfect_tolerance:
        return 10.0
    if error >= fail_tolerance:
        return 0.0

    return 10.0 * (1.0 - (error - perfect_tolerance) / (fail_tolerance - perfect_tolerance))


def score_by_max(value: float, perfect_max: float, fail_max: float) -> float:
    # Smaller value is better: 10 at/below perfect_max, 0 at/above fail_max,
    # linear ramp in between: 10 * (1 - (value - perfect_max)/(fail_max - perfect_max)).
    if math.isnan(value):
        return 0.0
    if value <= perfect_max:
        return 10.0
    if value >= fail_max:
        return 0.0
    return 10.0 * (1.0 - (value - perfect_max) / (fail_max - perfect_max))


@dataclass
class FrameScore:
    total: float
    arms_straight: float
    swing_spread: float
    legs_straight: float
    fist: float
    thumb: float

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 2),
            "arms_straight": round(self.arms_straight, 2),
            "swing_spread": round(self.swing_spread, 2),
            "legs_straight": round(self.legs_straight, 2),
            "fist": round(self.fist, 2),
            "thumb": round(self.thumb, 2),
        }


def score_swing_frame(
    *,
    inter_arm_angle_deg: float,
    left_elbow_angle_deg: float,
    right_elbow_angle_deg: float,
    left_knee_angle_deg: float,
    right_knee_angle_deg: float,
    fist_score: float,
    thumb_score: float,
    difficulty: float,
    target_arm_angle_deg: float,
    target_inter_arm_angle_deg: float,
    target_knee_angle_deg: float,
) -> FrameScore:
    """Score one swing key frame out of 10 (§6.2-§6.7).

    fist_score / thumb_score are already scored /10 by hand_analysis (they need
    hand landmarks and are difficulty-scaled there); this function scores the
    three pose parameters and combines all five with the config weights.
    """
    # Difficulty-scaled tolerances (all flow through scaled_tolerances, §7).
    arm_perfect, arm_fail = scaled_tolerances(difficulty, *cfg.ELBOW_STRAIGHT_BAND)
    inter_perfect, inter_fail = scaled_tolerances(difficulty, *cfg.INTER_ARM_BAND)
    knee_perfect, knee_fail = scaled_tolerances(difficulty, *cfg.KNEE_STRAIGHT_BAND)

    # arms_straight = mean(score(elbow_L vs 180), score(elbow_R vs 180))  (§6.2)
    left_arm = score_by_tolerance(left_elbow_angle_deg, target_arm_angle_deg, arm_perfect, arm_fail)
    right_arm = score_by_tolerance(right_elbow_angle_deg, target_arm_angle_deg, arm_perfect, arm_fail)
    arms_straight = float(np.mean([left_arm, right_arm]))

    # swing_spread = score(inter_arm_angle vs 180)  (§6.3)
    swing_spread = score_by_tolerance(
        inter_arm_angle_deg, target_inter_arm_angle_deg, inter_perfect, inter_fail
    )

    # legs_straight = mean(score(knee_L vs 180), score(knee_R vs 180))  (§6.4)
    left_leg = score_by_tolerance(left_knee_angle_deg, target_knee_angle_deg, knee_perfect, knee_fail)
    right_leg = score_by_tolerance(right_knee_angle_deg, target_knee_angle_deg, knee_perfect, knee_fail)
    legs_straight = float(np.mean([left_leg, right_leg]))

    # frame_total = sum(param_score * weight)  (§6.7)
    w = cfg.WEIGHTS
    total = (
        arms_straight * w["arms_straight"]
        + swing_spread * w["swing_spread"]
        + legs_straight * w["legs_straight"]
        + fist_score * w["fist"]
        + thumb_score * w["thumb"]
    )

    return FrameScore(
        total=total,
        arms_straight=arms_straight,
        swing_spread=swing_spread,
        legs_straight=legs_straight,
        fist=fist_score,
        thumb=thumb_score,
    )
