from __future__ import annotations

from dataclasses import dataclass

from .geometry import angle_at_joint

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
LEFT_FOOT_INDEX = 31
RIGHT_FOOT_INDEX = 32


@dataclass
class LegAngles:
    knee_angle_deg: float
    foot_angle_deg: float
    knee_lift_px: float


@dataclass
class PeakFrameMetrics:
    frame_index: int
    timestamp_ms: float
    peak_leg: str
    peak_knee_lift_px: float
    left: LegAngles
    right: LegAngles
    left_elbow_angle_deg: float
    right_elbow_angle_deg: float
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

    @property
    def peak_knee_angle_deg(self) -> float:
        return self.left.knee_angle_deg if self.peak_leg == "left" else self.right.knee_angle_deg

    @property
    def peak_foot_angle_deg(self) -> float:
        return self.left.foot_angle_deg if self.peak_leg == "left" else self.right.foot_angle_deg

    @property
    def grounded_knee_angle_deg(self) -> float:
        return self.right.knee_angle_deg if self.peak_leg == "left" else self.left.knee_angle_deg


def _to_pixel(landmark, width: int, height: int) -> tuple[float, float]:
    return float(landmark.x * width), float(landmark.y * height)


def _leg_angles(
    hip_px: tuple[float, float],
    knee_px: tuple[float, float],
    ankle_px: tuple[float, float],
    foot_px: tuple[float, float],
) -> LegAngles:
    knee_angle = angle_at_joint(hip_px, knee_px, ankle_px)
    foot_angle = angle_at_joint(knee_px, ankle_px, foot_px)
    knee_lift = hip_px[1] - knee_px[1]
    return LegAngles(
        knee_angle_deg=knee_angle,
        foot_angle_deg=foot_angle,
        knee_lift_px=knee_lift,
    )


def compute_peak_frame_metrics(
    pose_landmarks,
    frame_index: int,
    timestamp_ms: float,
    width: int,
    height: int,
) -> PeakFrameMetrics | None:
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

    left = _leg_angles(left_hip_px, left_knee_px, left_ankle_px, left_foot_px)
    right = _leg_angles(right_hip_px, right_knee_px, right_ankle_px, right_foot_px)
    left_elbow_angle = angle_at_joint(left_shoulder_px, left_elbow_px, left_wrist_px)
    right_elbow_angle = angle_at_joint(right_shoulder_px, right_elbow_px, right_wrist_px)

    if left.knee_lift_px >= right.knee_lift_px:
        peak_leg = "left"
        peak_lift = left.knee_lift_px
    else:
        peak_leg = "right"
        peak_lift = right.knee_lift_px

    return PeakFrameMetrics(
        frame_index=frame_index,
        timestamp_ms=timestamp_ms,
        peak_leg=peak_leg,
        peak_knee_lift_px=peak_lift,
        left=left,
        right=right,
        left_elbow_angle_deg=left_elbow_angle,
        right_elbow_angle_deg=right_elbow_angle,
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
    )
