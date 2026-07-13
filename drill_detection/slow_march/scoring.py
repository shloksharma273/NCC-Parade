from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .difficulty import scaled_tolerances


# --------------------------------------------------------------------------------------
# Scoring primitives (copied VERBATIM so the package is self-contained):
#   score_by_tolerance  <- kadam_tal/scoring.py
#   score_by_max        <- salute/geometry.py
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

    # Linear ramp: 10 at the perfect edge, 0 at the fail edge.
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
# See MATH.md section "Difficulty scaling" for the full table.
# --------------------------------------------------------------------------------------
ARM_BAND = (8.0, 3.0, 45.0, 18.0)               # elbow angle error vs 180 deg
HEAD_YAW_BAND = (0.20, 0.06, 0.55, 0.30)        # |yaw ratio| via score_by_max (perfect_max, fail_max at easy/hard)
HEAD_TILT_BAND = (8.0, 3.0, 35.0, 15.0)         # head tilt error vs 0 deg
GROUNDED_KNEE_BAND = (6.0, 2.0, 35.0, 12.0)     # grounded knee angle error vs 180 deg
GROUNDED_VERTICAL_BAND = (8.0, 3.0, 35.0, 15.0) # grounded leg vertical error vs 0 deg
RAISED_FOOT_BAND = (6.0, 3.0, 30.0, 12.0)       # raised foot horizontal error vs 0 deg

# Head-yaw is unreliable from the side (PRD clarified decision): keep the formula intact
# but down-weight the yaw sub-check inside head_front so it does not dominate.
SIDE_VIEW_YAW_WEIGHT = 0.25
FRONT_VIEW_YAW_WEIGHT = 0.5

# Per-parameter weights for the frame total (PRD 6.6). Sum == 1.0.
PARAM_WEIGHTS = {
    "hands": 0.25,
    "head_front": 0.25,
    "grounded_leg": 0.25,
    "raised_foot": 0.25,
}


@dataclass
class FrameScore:
    total: float          # after the mandatory raised-foot gate
    total_pre_gate: float # before the gate (diagnostic)
    hands: float
    head_front: float
    grounded_leg: float
    raised_foot: float
    gated: bool           # True if the mandatory raised-foot gate fired

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 2),
            "total_pre_gate": round(self.total_pre_gate, 2),
            "hands": round(self.hands, 2),
            "head_front": round(self.head_front, 2),
            "grounded_leg": round(self.grounded_leg, 2),
            "raised_foot": round(self.raised_foot, 2),
            "gated": self.gated,
        }


def apply_raised_foot_gate(
    frame_total: float,
    raised_foot_score: float,
    is_mandatory: bool,
    pass_threshold: float,
    gate_cap: float,
) -> tuple[float, bool]:
    """MANDATORY gate (PRD 6.5): if the raised-foot sub-score fails, cap the frame total.

    if is_mandatory and raised_foot_score < pass_threshold:
        frame_total = min(frame_total, gate_cap)   # cap at 4.0, NOT zero
    """
    if is_mandatory and raised_foot_score < pass_threshold:
        return min(frame_total, gate_cap), True
    return frame_total, False


def score_frame(
    *,
    left_elbow_angle_deg: float,
    right_elbow_angle_deg: float,
    head_yaw_ratio: float,
    head_tilt_deg: float,
    grounded_knee_angle_deg: float,
    grounded_vertical_deg: float,
    raised_foot_horizontal_deg: float,
    difficulty: float,
    view: str = "side",
    target_arm_angle_deg: float = 180.0,
    target_grounded_knee_deg: float = 180.0,
    target_grounded_vertical_deg: float = 0.0,
    target_foot_horizontal_deg: float = 0.0,
    raised_foot_is_mandatory: bool = True,
    raised_foot_pass_threshold: float = 5.0,
    raised_foot_gate_cap: float = 4.0,
) -> FrameScore:
    """Score one key frame /10 across the four slow-march parameters, then apply the gate."""

    # --- 6.2 Arms straight: elbow angle vs 180 deg, averaged L/R ---
    arm_perfect, arm_fail = scaled_tolerances(difficulty, *ARM_BAND)
    left_arm = score_by_tolerance(left_elbow_angle_deg, target_arm_angle_deg, arm_perfect, arm_fail)
    right_arm = score_by_tolerance(right_elbow_angle_deg, target_arm_angle_deg, arm_perfect, arm_fail)
    hands = float(np.mean([left_arm, right_arm]))

    # --- 6.3 Look to the front: mean of (yaw score, neck-tilt score) ---
    yaw_perfect, yaw_fail = scaled_tolerances(difficulty, *HEAD_YAW_BAND)
    # yaw_ratio ~ 0 facing front; score_by_max penalises magnitude of the ratio
    yaw_score = score_by_max(abs(head_yaw_ratio) if not math.isnan(head_yaw_ratio) else float("nan"),
                             yaw_perfect, yaw_fail)
    tilt_perfect, tilt_fail = scaled_tolerances(difficulty, *HEAD_TILT_BAND)
    tilt_score = score_by_tolerance(head_tilt_deg, 0.0, tilt_perfect, tilt_fail)
    # Side view: yaw is unreliable, down-weight it (formula kept intact & documented).
    yaw_w = SIDE_VIEW_YAW_WEIGHT if view == "side" else FRONT_VIEW_YAW_WEIGHT
    head_front = yaw_w * yaw_score + (1.0 - yaw_w) * tilt_score

    # --- 6.4 Grounded leg perpendicular & straight: mean of (knee, vertical) ---
    knee_perfect, knee_fail = scaled_tolerances(difficulty, *GROUNDED_KNEE_BAND)
    grounded_knee = score_by_tolerance(grounded_knee_angle_deg, target_grounded_knee_deg, knee_perfect, knee_fail)
    vert_perfect, vert_fail = scaled_tolerances(difficulty, *GROUNDED_VERTICAL_BAND)
    grounded_vert = score_by_tolerance(grounded_vertical_deg, target_grounded_vertical_deg, vert_perfect, vert_fail)
    grounded_leg = float(np.mean([grounded_knee, grounded_vert]))

    # --- 6.5 Raised foot parallel to ground (MANDATORY sub-check) ---
    foot_perfect, foot_fail = scaled_tolerances(difficulty, *RAISED_FOOT_BAND)
    raised_foot = score_by_tolerance(raised_foot_horizontal_deg, target_foot_horizontal_deg, foot_perfect, foot_fail)

    # --- 6.6 Frame total = weighted sum, then apply the mandatory gate ---
    total_pre_gate = (
        hands * PARAM_WEIGHTS["hands"]
        + head_front * PARAM_WEIGHTS["head_front"]
        + grounded_leg * PARAM_WEIGHTS["grounded_leg"]
        + raised_foot * PARAM_WEIGHTS["raised_foot"]
    )
    total, gated = apply_raised_foot_gate(
        total_pre_gate,
        raised_foot,
        raised_foot_is_mandatory,
        raised_foot_pass_threshold,
        raised_foot_gate_cap,
    )

    return FrameScore(
        total=total,
        total_pre_gate=total_pre_gate,
        hands=hands,
        head_front=head_front,
        grounded_leg=grounded_leg,
        raised_foot=raised_foot,
        gated=gated,
    )
