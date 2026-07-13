from __future__ import annotations

from dataclasses import dataclass

from .geometry import angle_at_joint, angle_between, to_pixel

# --- Pose landmark indices (§5.1, same as kadam_tal) -----------------------
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


@dataclass
class BajuSwingFrameMetrics:
    frame_index: int
    timestamp_ms: float
    # Key-frame signal: angle between the two arm vectors (§6.1).
    inter_arm_angle_deg: float
    # Elbow angles (arms straight, §6.2).
    left_elbow_angle_deg: float
    right_elbow_angle_deg: float
    # Knee angles (legs straight, §6.4).
    left_knee_angle_deg: float
    right_knee_angle_deg: float
    # Pixel coords for annotation.
    left_shoulder_px: tuple[float, float]
    left_elbow_px: tuple[float, float]
    left_wrist_px: tuple[float, float]
    right_shoulder_px: tuple[float, float]
    right_elbow_px: tuple[float, float]
    right_wrist_px: tuple[float, float]
    left_hip_px: tuple[float, float]
    left_knee_px: tuple[float, float]
    left_ankle_px: tuple[float, float]
    right_hip_px: tuple[float, float]
    right_knee_px: tuple[float, float]
    right_ankle_px: tuple[float, float]


def _pt(px: tuple[float, float]) -> tuple[float, float]:
    return (float(px[0]), float(px[1]))


def compute_frame_metrics(
    pose_landmarks,
    frame_index: int,
    timestamp_ms: float,
    width: int,
    height: int,
) -> BajuSwingFrameMetrics | None:
    if not pose_landmarks or len(pose_landmarks) <= RIGHT_ANKLE:
        return None

    ls = to_pixel(pose_landmarks[LEFT_SHOULDER], width, height)
    rs = to_pixel(pose_landmarks[RIGHT_SHOULDER], width, height)
    le = to_pixel(pose_landmarks[LEFT_ELBOW], width, height)
    re = to_pixel(pose_landmarks[RIGHT_ELBOW], width, height)
    lw = to_pixel(pose_landmarks[LEFT_WRIST], width, height)
    rw = to_pixel(pose_landmarks[RIGHT_WRIST], width, height)
    lh = to_pixel(pose_landmarks[LEFT_HIP], width, height)
    rh = to_pixel(pose_landmarks[RIGHT_HIP], width, height)
    lk = to_pixel(pose_landmarks[LEFT_KNEE], width, height)
    rk = to_pixel(pose_landmarks[RIGHT_KNEE], width, height)
    la = to_pixel(pose_landmarks[LEFT_ANKLE], width, height)
    ra = to_pixel(pose_landmarks[RIGHT_ANKLE], width, height)

    # Inter-arm angle (§6.1): a_L = wrist_L - shoulder_L, a_R = wrist_R - shoulder_R
    #   inter_arm_angle = angle_between(a_L, a_R)
    inter_arm_angle = angle_between(lw - ls, rw - rs)

    # Elbow interior angles (§6.2): angle_at_joint(shoulder, elbow, wrist)
    left_elbow_angle = angle_at_joint(ls, le, lw)
    right_elbow_angle = angle_at_joint(rs, re, rw)

    # Knee interior angles (§6.4): angle_at_joint(hip, knee, ankle)
    left_knee_angle = angle_at_joint(lh, lk, la)
    right_knee_angle = angle_at_joint(rh, rk, ra)

    return BajuSwingFrameMetrics(
        frame_index=frame_index,
        timestamp_ms=timestamp_ms,
        inter_arm_angle_deg=inter_arm_angle,
        left_elbow_angle_deg=left_elbow_angle,
        right_elbow_angle_deg=right_elbow_angle,
        left_knee_angle_deg=left_knee_angle,
        right_knee_angle_deg=right_knee_angle,
        left_shoulder_px=_pt(ls),
        left_elbow_px=_pt(le),
        left_wrist_px=_pt(lw),
        right_shoulder_px=_pt(rs),
        right_elbow_px=_pt(re),
        right_wrist_px=_pt(rw),
        left_hip_px=_pt(lh),
        left_knee_px=_pt(lk),
        left_ankle_px=_pt(la),
        right_hip_px=_pt(rh),
        right_knee_px=_pt(rk),
        right_ankle_px=_pt(ra),
    )
