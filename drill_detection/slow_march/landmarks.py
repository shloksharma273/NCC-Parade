from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geometry import angle_at_joint, angle_between, angle_to_horizontal, angle_to_vertical

# --- MediaPipe Holistic pose indices (identical set to kadam_tal) ---
NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_HEEL = 29
RIGHT_HEEL = 30
LEFT_FOOT_INDEX = 31
RIGHT_FOOT_INDEX = 32


@dataclass
class LegAngles:
    knee_angle_deg: float          # angle_at_joint(hip, knee, ankle); 180 == straight
    foot_horizontal_deg: float     # angle_to_horizontal(foot_index - heel); 0 == flat/parallel
    vertical_deg: float            # angle_to_vertical(ankle - hip); 0 == leg perpendicular to ground
    knee_lift_px: float            # hip_y - knee_y (kadam_tal convention); larger == knee raised higher


@dataclass
class SlowMarchFrameMetrics:
    frame_index: int
    timestamp_ms: float

    inter_leg_angle_deg: float     # KEY SIGNAL: angle between the two thigh vectors
    grounded_leg: str              # "left" / "right" (planted, smaller knee-lift)
    raised_leg: str                # "left" / "right" (airborne, larger knee-lift)

    left: LegAngles
    right: LegAngles

    left_elbow_angle_deg: float
    right_elbow_angle_deg: float

    head_yaw_ratio: float          # (nose_x - shoulder_mid_x) / shoulder_width; 0 == facing front
    head_tilt_deg: float           # angle_to_vertical(nose - shoulder_mid); 0 == upright

    # pixel coords for annotation
    left_hip_px: tuple[float, float]
    left_knee_px: tuple[float, float]
    left_ankle_px: tuple[float, float]
    left_heel_px: tuple[float, float]
    left_foot_px: tuple[float, float]
    right_hip_px: tuple[float, float]
    right_knee_px: tuple[float, float]
    right_ankle_px: tuple[float, float]
    right_heel_px: tuple[float, float]
    right_foot_px: tuple[float, float]
    left_shoulder_px: tuple[float, float]
    left_elbow_px: tuple[float, float]
    left_wrist_px: tuple[float, float]
    right_shoulder_px: tuple[float, float]
    right_elbow_px: tuple[float, float]
    right_wrist_px: tuple[float, float]
    nose_px: tuple[float, float]

    # convenience accessors resolving grounded/raised leg to concrete angle values
    @property
    def grounded(self) -> LegAngles:
        return self.left if self.grounded_leg == "left" else self.right

    @property
    def raised(self) -> LegAngles:
        return self.left if self.raised_leg == "left" else self.right

    @property
    def grounded_knee_angle_deg(self) -> float:
        return self.grounded.knee_angle_deg

    @property
    def grounded_vertical_deg(self) -> float:
        return self.grounded.vertical_deg

    @property
    def raised_foot_horizontal_deg(self) -> float:
        return self.raised.foot_horizontal_deg


def _to_pixel(landmark, width: int, height: int) -> tuple[float, float]:
    return float(landmark.x * width), float(landmark.y * height)


def _leg_angles(
    hip_px: tuple[float, float],
    knee_px: tuple[float, float],
    ankle_px: tuple[float, float],
    heel_px: tuple[float, float],
    foot_px: tuple[float, float],
) -> LegAngles:
    knee_angle = angle_at_joint(hip_px, knee_px, ankle_px)         # 180 deg == straight knee
    # foot vector f = foot_index - heel; angle_to_horizontal(f) == 0 when foot is flat/parallel
    foot_horizontal = angle_to_horizontal(np.array(foot_px) - np.array(heel_px))
    # leg vertical: ankle - hip; angle_to_vertical == 0 when leg perpendicular to ground
    vertical = angle_to_vertical(np.array(ankle_px) - np.array(hip_px))
    knee_lift = hip_px[1] - knee_px[1]                             # hip_y - knee_y (raised => larger)
    return LegAngles(
        knee_angle_deg=knee_angle,
        foot_horizontal_deg=foot_horizontal,
        vertical_deg=vertical,
        knee_lift_px=knee_lift,
    )


def compute_frame_metrics(
    pose_landmarks,
    frame_index: int,
    timestamp_ms: float,
    width: int,
    height: int,
) -> SlowMarchFrameMetrics | None:
    if not pose_landmarks:
        return None

    left_shoulder_px = _to_pixel(pose_landmarks[LEFT_SHOULDER], width, height)
    right_shoulder_px = _to_pixel(pose_landmarks[RIGHT_SHOULDER], width, height)
    left_elbow_px = _to_pixel(pose_landmarks[LEFT_ELBOW], width, height)
    right_elbow_px = _to_pixel(pose_landmarks[RIGHT_ELBOW], width, height)
    left_wrist_px = _to_pixel(pose_landmarks[LEFT_WRIST], width, height)
    right_wrist_px = _to_pixel(pose_landmarks[RIGHT_WRIST], width, height)
    left_hip_px = _to_pixel(pose_landmarks[LEFT_HIP], width, height)
    right_hip_px = _to_pixel(pose_landmarks[RIGHT_HIP], width, height)
    left_knee_px = _to_pixel(pose_landmarks[LEFT_KNEE], width, height)
    right_knee_px = _to_pixel(pose_landmarks[RIGHT_KNEE], width, height)
    left_ankle_px = _to_pixel(pose_landmarks[LEFT_ANKLE], width, height)
    right_ankle_px = _to_pixel(pose_landmarks[RIGHT_ANKLE], width, height)
    left_heel_px = _to_pixel(pose_landmarks[LEFT_HEEL], width, height)
    right_heel_px = _to_pixel(pose_landmarks[RIGHT_HEEL], width, height)
    left_foot_px = _to_pixel(pose_landmarks[LEFT_FOOT_INDEX], width, height)
    right_foot_px = _to_pixel(pose_landmarks[RIGHT_FOOT_INDEX], width, height)
    nose_px = _to_pixel(pose_landmarks[NOSE], width, height)

    left = _leg_angles(left_hip_px, left_knee_px, left_ankle_px, left_heel_px, left_foot_px)
    right = _leg_angles(right_hip_px, right_knee_px, right_ankle_px, right_heel_px, right_foot_px)

    left_elbow_angle = angle_at_joint(left_shoulder_px, left_elbow_px, left_wrist_px)
    right_elbow_angle = angle_at_joint(right_shoulder_px, right_elbow_px, right_wrist_px)

    # --- KEY SIGNAL: inter-leg angle between thigh vectors v = knee - hip ---
    v_left = np.array(left_knee_px) - np.array(left_hip_px)
    v_right = np.array(right_knee_px) - np.array(right_hip_px)
    inter_leg_angle = angle_between(v_left, v_right)  # small at stance, peaks at step extreme

    # --- Head "look front" (v1 pose-nose approximation, PRD 6.3) ---
    # HOOK: swap in Holistic face-landmark yaw here for higher accuracy later.
    shoulder_mid_x = (left_shoulder_px[0] + right_shoulder_px[0]) / 2.0
    shoulder_mid_y = (left_shoulder_px[1] + right_shoulder_px[1]) / 2.0
    shoulder_width = abs(left_shoulder_px[0] - right_shoulder_px[0])
    if shoulder_width <= 1e-6:
        head_yaw_ratio = float("nan")
    else:
        head_yaw_ratio = (nose_px[0] - shoulder_mid_x) / shoulder_width  # ~0 facing front
    head_tilt = angle_to_vertical(np.array(nose_px) - np.array([shoulder_mid_x, shoulder_mid_y]))

    # grounded = smaller knee-lift (planted, lower on screen); raised = the other
    if left.knee_lift_px <= right.knee_lift_px:
        grounded_leg, raised_leg = "left", "right"
    else:
        grounded_leg, raised_leg = "right", "left"

    return SlowMarchFrameMetrics(
        frame_index=frame_index,
        timestamp_ms=timestamp_ms,
        inter_leg_angle_deg=inter_leg_angle,
        grounded_leg=grounded_leg,
        raised_leg=raised_leg,
        left=left,
        right=right,
        left_elbow_angle_deg=left_elbow_angle,
        right_elbow_angle_deg=right_elbow_angle,
        head_yaw_ratio=head_yaw_ratio,
        head_tilt_deg=head_tilt,
        left_hip_px=left_hip_px,
        left_knee_px=left_knee_px,
        left_ankle_px=left_ankle_px,
        left_heel_px=left_heel_px,
        left_foot_px=left_foot_px,
        right_hip_px=right_hip_px,
        right_knee_px=right_knee_px,
        right_ankle_px=right_ankle_px,
        right_heel_px=right_heel_px,
        right_foot_px=right_foot_px,
        left_shoulder_px=left_shoulder_px,
        left_elbow_px=left_elbow_px,
        left_wrist_px=left_wrist_px,
        right_shoulder_px=right_shoulder_px,
        right_elbow_px=right_elbow_px,
        right_wrist_px=right_wrist_px,
        nose_px=nose_px,
    )
