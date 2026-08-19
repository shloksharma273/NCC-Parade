from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geometry import angle_at_joint, angle_between, angle_to_vertical

# --- MediaPipe Holistic pose indices (identical set to slow_march / kadam_tal) ---
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
class HillMarchFrameMetrics:
    frame_index: int
    timestamp_ms: float

    # KEY SIGNAL + parameter 1: angle between the two legs (separation). Peaks == step extremes.
    inter_leg_angle_deg: float

    # Parameter 2 (arms straight + close to body).
    left_elbow_angle_deg: float
    right_elbow_angle_deg: float
    left_arm_abduction_deg: float   # angle between (shoulder->elbow) and (shoulder->hip); 0 == alongside torso
    right_arm_abduction_deg: float

    # Parameter 3 (legs straight).
    left_knee_angle_deg: float
    right_knee_angle_deg: float

    # Parameter 4 (head straight).
    head_yaw_ratio: float           # (nose_x - shoulder_mid_x) / shoulder_width; 0 == facing front
    head_tilt_deg: float            # angle_to_vertical(nose - shoulder_mid); 0 == upright

    # pixel coords for annotation
    left_hip_px: tuple[float, float]
    left_knee_px: tuple[float, float]
    left_ankle_px: tuple[float, float]
    left_foot_px: tuple[float, float]
    right_hip_px: tuple[float, float]
    right_knee_px: tuple[float, float]
    right_ankle_px: tuple[float, float]
    right_foot_px: tuple[float, float]
    left_shoulder_px: tuple[float, float]
    left_elbow_px: tuple[float, float]
    left_wrist_px: tuple[float, float]
    right_shoulder_px: tuple[float, float]
    right_elbow_px: tuple[float, float]
    right_wrist_px: tuple[float, float]
    nose_px: tuple[float, float]


def _to_pixel(landmark, width: int, height: int) -> tuple[float, float]:
    return float(landmark.x * width), float(landmark.y * height)


def _inter_leg_angle(left_hip, left_knee, left_ankle, right_hip, right_knee, right_ankle, vector: str) -> float:
    """Angle between the two legs (separation). `vector` selects the leg definition."""
    if vector == "hip_knee":  # thigh only — robust when the ankle blurs / occludes
        v_left = np.array(left_knee) - np.array(left_hip)
        v_right = np.array(right_knee) - np.array(right_hip)
    else:  # "hip_ankle" — the full leg, i.e. the literal angle between the two legs
        v_left = np.array(left_ankle) - np.array(left_hip)
        v_right = np.array(right_ankle) - np.array(right_hip)
    return angle_between(v_left, v_right)


def compute_frame_metrics(
    pose_landmarks,
    frame_index: int,
    timestamp_ms: float,
    width: int,
    height: int,
    inter_leg_vector: str = "hip_ankle",
) -> HillMarchFrameMetrics | None:
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
    left_foot_px = _to_pixel(pose_landmarks[LEFT_FOOT_INDEX], width, height)
    right_foot_px = _to_pixel(pose_landmarks[RIGHT_FOOT_INDEX], width, height)
    nose_px = _to_pixel(pose_landmarks[NOSE], width, height)

    inter_leg_angle = _inter_leg_angle(
        left_hip_px, left_knee_px, left_ankle_px,
        right_hip_px, right_knee_px, right_ankle_px,
        inter_leg_vector,
    )

    # Arms straight: elbow interior angle (shoulder-elbow-wrist); 180 == straight.
    left_elbow_angle = angle_at_joint(left_shoulder_px, left_elbow_px, left_wrist_px)
    right_elbow_angle = angle_at_joint(right_shoulder_px, right_elbow_px, right_wrist_px)
    # Arms close to body: abduction = angle at the shoulder between the upper arm
    # (shoulder->elbow) and the torso (shoulder->hip). 0 == arm held alongside the body.
    left_arm_abduction = angle_at_joint(left_elbow_px, left_shoulder_px, left_hip_px)
    right_arm_abduction = angle_at_joint(right_elbow_px, right_shoulder_px, right_hip_px)

    # Legs straight: knee interior angle (hip-knee-ankle); 180 == straight.
    left_knee_angle = angle_at_joint(left_hip_px, left_knee_px, left_ankle_px)
    right_knee_angle = angle_at_joint(right_hip_px, right_knee_px, right_ankle_px)

    # Head straight: yaw ratio (facing front) + tilt (upright).
    shoulder_mid_x = (left_shoulder_px[0] + right_shoulder_px[0]) / 2.0
    shoulder_mid_y = (left_shoulder_px[1] + right_shoulder_px[1]) / 2.0
    shoulder_width = abs(left_shoulder_px[0] - right_shoulder_px[0])
    head_yaw_ratio = float("nan") if shoulder_width <= 1e-6 else (nose_px[0] - shoulder_mid_x) / shoulder_width
    head_tilt = angle_to_vertical(np.array(nose_px) - np.array([shoulder_mid_x, shoulder_mid_y]))

    return HillMarchFrameMetrics(
        frame_index=frame_index,
        timestamp_ms=timestamp_ms,
        inter_leg_angle_deg=inter_leg_angle,
        left_elbow_angle_deg=left_elbow_angle,
        right_elbow_angle_deg=right_elbow_angle,
        left_arm_abduction_deg=left_arm_abduction,
        right_arm_abduction_deg=right_arm_abduction,
        left_knee_angle_deg=left_knee_angle,
        right_knee_angle_deg=right_knee_angle,
        head_yaw_ratio=head_yaw_ratio,
        head_tilt_deg=head_tilt,
        left_hip_px=left_hip_px,
        left_knee_px=left_knee_px,
        left_ankle_px=left_ankle_px,
        left_foot_px=left_foot_px,
        right_hip_px=right_hip_px,
        right_knee_px=right_knee_px,
        right_ankle_px=right_ankle_px,
        right_foot_px=right_foot_px,
        left_shoulder_px=left_shoulder_px,
        left_elbow_px=left_elbow_px,
        left_wrist_px=left_wrist_px,
        right_shoulder_px=right_shoulder_px,
        right_elbow_px=right_elbow_px,
        right_wrist_px=right_wrist_px,
        nose_px=nose_px,
    )
