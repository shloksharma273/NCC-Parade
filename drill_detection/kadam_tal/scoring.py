from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .difficulty import scaled_tolerances


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


@dataclass
class FrameScore:
    total: float
    peak_knee_angle: float
    peak_foot_angle: float
    grounded_leg: float
    hands: float

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 2),
            "peak_knee_angle": round(self.peak_knee_angle, 2),
            "peak_foot_angle": round(self.peak_foot_angle, 2),
            "grounded_leg": round(self.grounded_leg, 2),
            "hands": round(self.hands, 2),
        }


def score_peak_frame(
    peak_knee_angle_deg: float,
    peak_foot_angle_deg: float,
    grounded_knee_angle_deg: float,
    left_elbow_angle_deg: float,
    right_elbow_angle_deg: float,
    difficulty: float,
) -> FrameScore:
    knee_perfect, knee_fail = scaled_tolerances(difficulty, 5.0, 2.0, 40.0, 15.0)
    foot_perfect, foot_fail = scaled_tolerances(difficulty, 5.0, 2.0, 40.0, 15.0)
    leg_perfect, leg_fail = scaled_tolerances(difficulty, 5.0, 2.0, 35.0, 12.0)
    arm_perfect, arm_fail = scaled_tolerances(difficulty, 6.0, 2.5, 45.0, 18.0)

    peak_knee = score_by_tolerance(peak_knee_angle_deg, 90.0, knee_perfect, knee_fail)
    peak_foot = score_by_tolerance(peak_foot_angle_deg, 90.0, foot_perfect, foot_fail)
    grounded = score_by_tolerance(grounded_knee_angle_deg, 180.0, leg_perfect, leg_fail)

    left_arm = score_by_tolerance(left_elbow_angle_deg, 180.0, arm_perfect, arm_fail)
    right_arm = score_by_tolerance(right_elbow_angle_deg, 180.0, arm_perfect, arm_fail)
    hands = float(np.mean([left_arm, right_arm]))

    weights = {
        "peak_knee_angle": 0.25,
        "peak_foot_angle": 0.25,
        "grounded_leg": 0.25,
        "hands": 0.25,
    }
    total = (
        peak_knee * weights["peak_knee_angle"]
        + peak_foot * weights["peak_foot_angle"]
        + grounded * weights["grounded_leg"]
        + hands * weights["hands"]
    )

    return FrameScore(
        total=total,
        peak_knee_angle=peak_knee,
        peak_foot_angle=peak_foot,
        grounded_leg=grounded,
        hands=hands,
    )
