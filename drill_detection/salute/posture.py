from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HolisticLandmarker,
    HolisticLandmarkerOptions,
    HolisticLandmarkerResult,
    RunningMode,
)
from mediapipe.tasks.python.vision.hand_landmarker import HandLandmark
from mediapipe.tasks.python.vision.pose_landmarker import PoseLandmark

from .difficulty import DifficultyProfile
from .geometry import (
    angle_at_joint,
    angle_between,
    perpendicular_separation,
    to_pixel,
)
from .landmarks import FrameMetrics
from .mediapipe_models import ensure_models

POSTURE_WEIGHTS = {
    "fingers_joined": 0.25,
    "elbow_angle": 0.25,
    "heels": 0.25,
    "left_hand_attached": 0.25,
}

TARGET_ELBOW_ANGLE = 45.0
TARGET_HEEL_ANGLE = 30.0


@dataclass
class PostureAnalysis:
    rank: int
    frame_index: int
    timestamp_ms: float
    finger_mid_perp_width_ratio: float
    finger_mcp_perp_width_ratio: float
    finger_width_diff_ratio: float
    fingers_joined_score: float
    elbow_angle_deg: float
    elbow_angle_score: float
    heel_distance_ratio: float  # Medial shoe-contact distance / foot length
    heel_angle_deg: float
    heel_touch_score: float
    heel_angle_score: float
    heels_score: float
    left_hand_body_distance_ratio: float
    left_hand_attached_score: float
    weighted_score: float
    difficulty: float
    output_image_path: str


def is_front_salute_video(video_path: Path) -> bool:
    return "front" in video_path.stem.lower()


def _pose_point(result: HolisticLandmarkerResult, index: int, width: int, height: int) -> np.ndarray | None:
    if not result.pose_landmarks or index >= len(result.pose_landmarks):
        return None
    return to_pixel(result.pose_landmarks[index], width, height)


def _hand_point(hand_landmarks, index: int, width: int, height: int) -> np.ndarray:
    return to_pixel(hand_landmarks[index], width, height)


def _hand_scale(right_hand, width: int, height: int) -> float:
    wrist = _hand_point(right_hand, int(HandLandmark.WRIST), width, height)
    middle_mcp = _hand_point(right_hand, int(HandLandmark.MIDDLE_FINGER_MCP), width, height)
    scale = float(np.linalg.norm(wrist - middle_mcp))
    return max(scale, 1.0)


def _finger_midpoint(hand_landmarks, pip_idx: int, dip_idx: int, width: int, height: int) -> np.ndarray:
    pip = _hand_point(hand_landmarks, pip_idx, width, height)
    dip = _hand_point(hand_landmarks, dip_idx, width, height)
    return (pip + dip) / 2.0


def _finger_axis(hand_landmarks, width: int, height: int) -> np.ndarray:
    middle_mcp = _hand_point(hand_landmarks, int(HandLandmark.MIDDLE_FINGER_MCP), width, height)
    middle_tip = _hand_point(hand_landmarks, int(HandLandmark.MIDDLE_FINGER_TIP), width, height)
    return middle_tip - middle_mcp


def _fingers_joined_metrics(
    result: HolisticLandmarkerResult,
    width: int,
    height: int,
    profile: DifficultyProfile,
) -> tuple[float, float, float, float]:
    if not result.right_hand_landmarks:
        return float("nan"), float("nan"), float("nan"), 0.0

    right_hand = result.right_hand_landmarks
    scale = _hand_scale(right_hand, width, height)
    finger_axis = _finger_axis(right_hand, width, height)

    index_mid = _finger_midpoint(
        right_hand,
        int(HandLandmark.INDEX_FINGER_PIP),
        int(HandLandmark.INDEX_FINGER_DIP),
        width,
        height,
    )
    pinky_mid = _finger_midpoint(
        right_hand,
        int(HandLandmark.PINKY_PIP),
        int(HandLandmark.PINKY_DIP),
        width,
        height,
    )
    index_mcp = _hand_point(right_hand, int(HandLandmark.INDEX_FINGER_MCP), width, height)
    pinky_mcp = _hand_point(right_hand, int(HandLandmark.PINKY_MCP), width, height)

    mid_perp_width = perpendicular_separation(index_mid, pinky_mid, finger_axis)
    mcp_perp_width = perpendicular_separation(index_mcp, pinky_mcp, finger_axis)

    mid_perp_width_ratio = mid_perp_width / scale
    mcp_perp_width_ratio = mcp_perp_width / scale
    width_diff_ratio = abs(mid_perp_width - mcp_perp_width) / scale

    fingers_score = profile.score_max(width_diff_ratio, perfect_max=0.05, fail_max=0.35)
    return mid_perp_width_ratio, mcp_perp_width_ratio, width_diff_ratio, fingers_score


def _elbow_angle_metrics(
    result: HolisticLandmarkerResult, width: int, height: int, profile: DifficultyProfile
) -> tuple[float, float]:
    shoulder = _pose_point(result, int(PoseLandmark.RIGHT_SHOULDER), width, height)
    elbow = _pose_point(result, int(PoseLandmark.RIGHT_ELBOW), width, height)
    wrist = _pose_point(result, int(PoseLandmark.RIGHT_WRIST), width, height)
    if shoulder is None or elbow is None or wrist is None:
        return float("nan"), 0.0

    elbow_angle = angle_at_joint(shoulder, elbow, wrist)
    score = profile.score_tolerance(
        elbow_angle, TARGET_ELBOW_ANGLE, perfect_tolerance=5.0, fail_tolerance=25.0
    )
    return elbow_angle, score


def _foot_length(heel: np.ndarray, toe: np.ndarray) -> float:
    return max(float(np.linalg.norm(toe - heel)), 1.0)


def _medial_foot_contact(
    heel: np.ndarray, toe: np.ndarray, ankle: np.ndarray, other_ankle: np.ndarray
) -> np.ndarray:
    """Estimate the inner shoe contact point near the ankle."""
    foot = toe - heel
    foot_len = float(np.linalg.norm(foot))
    if foot_len <= 1e-6:
        return ankle

    foot_u = foot / foot_len
    inward = np.array([-foot_u[1], foot_u[0]])
    if np.dot(inward, other_ankle - ankle) < 0:
        inward = -inward
    return ankle + inward * (0.25 * foot_len)


def _heels_metrics(
    result: HolisticLandmarkerResult, width: int, height: int, profile: DifficultyProfile
) -> tuple[float, float, float, float, float]:
    left_heel = _pose_point(result, int(PoseLandmark.LEFT_HEEL), width, height)
    right_heel = _pose_point(result, int(PoseLandmark.RIGHT_HEEL), width, height)
    left_ankle = _pose_point(result, int(PoseLandmark.LEFT_ANKLE), width, height)
    right_ankle = _pose_point(result, int(PoseLandmark.RIGHT_ANKLE), width, height)
    left_toe = _pose_point(result, int(PoseLandmark.LEFT_FOOT_INDEX), width, height)
    right_toe = _pose_point(result, int(PoseLandmark.RIGHT_FOOT_INDEX), width, height)

    if any(
        p is None
        for p in (left_heel, right_heel, left_ankle, right_ankle, left_toe, right_toe)
    ):
        return float("nan"), float("nan"), 0.0, 0.0, 0.0

    left_contact = _medial_foot_contact(left_heel, left_toe, left_ankle, right_ankle)
    right_contact = _medial_foot_contact(right_heel, right_toe, right_ankle, left_ankle)
    foot_length = (_foot_length(left_heel, left_toe) + _foot_length(right_heel, right_toe)) / 2.0

    foot_contact_distance_ratio = float(np.linalg.norm(left_contact - right_contact)) / foot_length
    touch_score = profile.score_max(foot_contact_distance_ratio, perfect_max=0.55, fail_max=0.95)

    left_foot_vec = left_toe - left_heel
    right_foot_vec = right_toe - right_heel
    heel_angle = angle_between(left_foot_vec, right_foot_vec)
    angle_score = profile.score_tolerance(
        heel_angle, TARGET_HEEL_ANGLE, perfect_tolerance=5.0, fail_tolerance=25.0
    )

    heels_score = (touch_score + angle_score) / 2.0
    return foot_contact_distance_ratio, heel_angle, touch_score, angle_score, heels_score


def _left_hand_attached_metrics(
    result: HolisticLandmarkerResult, width: int, height: int, profile: DifficultyProfile
) -> tuple[float, float]:
    left_wrist_pose = _pose_point(result, int(PoseLandmark.LEFT_WRIST), width, height)
    left_shoulder = _pose_point(result, int(PoseLandmark.LEFT_SHOULDER), width, height)
    left_hip = _pose_point(result, int(PoseLandmark.LEFT_HIP), width, height)

    if left_wrist_pose is None or left_shoulder is None or left_hip is None:
        return float("nan"), 0.0

    if result.left_hand_landmarks:
        left_wrist = _hand_point(result.left_hand_landmarks, int(HandLandmark.WRIST), width, height)
    else:
        left_wrist = left_wrist_pose

    torso_scale = float(np.linalg.norm(left_shoulder - left_hip))
    torso_scale = max(torso_scale, 1.0)
    distance_ratio = float(np.linalg.norm(left_wrist - left_hip)) / torso_scale

    score = profile.score_max(distance_ratio, perfect_max=0.35, fail_max=1.0)
    return distance_ratio, score


def analyze_posture(
    result: HolisticLandmarkerResult, width: int, height: int, profile: DifficultyProfile
) -> dict[str, float]:
    mid_width_ratio, mcp_width_ratio, width_diff_ratio, fingers_score = _fingers_joined_metrics(
        result, width, height, profile
    )
    elbow_angle, elbow_score = _elbow_angle_metrics(result, width, height, profile)
    foot_contact_ratio, heel_angle, touch_score, angle_score, heels_score = _heels_metrics(
        result, width, height, profile
    )
    left_hand_ratio, left_hand_score = _left_hand_attached_metrics(result, width, height, profile)

    weighted_score = (
        POSTURE_WEIGHTS["fingers_joined"] * fingers_score
        + POSTURE_WEIGHTS["elbow_angle"] * elbow_score
        + POSTURE_WEIGHTS["heels"] * heels_score
        + POSTURE_WEIGHTS["left_hand_attached"] * left_hand_score
    )

    return {
        "finger_mid_perp_width_ratio": mid_width_ratio,
        "finger_mcp_perp_width_ratio": mcp_width_ratio,
        "finger_width_diff_ratio": width_diff_ratio,
        "fingers_joined_score": fingers_score,
        "elbow_angle_deg": elbow_angle,
        "elbow_angle_score": elbow_score,
        "heel_distance_ratio": foot_contact_ratio,
        "heel_angle_deg": heel_angle,
        "heel_touch_score": touch_score,
        "heel_angle_score": angle_score,
        "heels_score": heels_score,
        "left_hand_body_distance_ratio": left_hand_ratio,
        "left_hand_attached_score": left_hand_score,
        "weighted_score": weighted_score,
        "difficulty": profile.level,
    }


def _draw_angle_arc(
    frame: np.ndarray,
    center: tuple[int, int],
    start_point: tuple[int, int],
    end_point: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    start_angle = int(np.degrees(np.arctan2(start_point[1] - center[1], start_point[0] - center[0])))
    end_angle = int(np.degrees(np.arctan2(end_point[1] - center[1], end_point[0] - center[0])))
    cv2.ellipse(frame, center, (40, 40), 0, start_angle, end_angle, color, 2)


def draw_posture_annotations(
    frame: np.ndarray,
    result: HolisticLandmarkerResult,
    metrics: dict[str, float],
) -> np.ndarray:
    rendered = frame.copy()
    height, width = rendered.shape[:2]

    if result.right_hand_landmarks:
        right_hand = result.right_hand_landmarks
        index_mid = _finger_midpoint(
            right_hand,
            int(HandLandmark.INDEX_FINGER_PIP),
            int(HandLandmark.INDEX_FINGER_DIP),
            width,
            height,
        ).astype(int)
        pinky_mid = _finger_midpoint(
            right_hand,
            int(HandLandmark.PINKY_PIP),
            int(HandLandmark.PINKY_DIP),
            width,
            height,
        ).astype(int)
        index_mcp = _hand_point(right_hand, int(HandLandmark.INDEX_FINGER_MCP), width, height).astype(int)
        pinky_mcp = _hand_point(right_hand, int(HandLandmark.PINKY_MCP), width, height).astype(int)

        for point in (index_mid, pinky_mid, index_mcp, pinky_mcp):
            cv2.circle(rendered, tuple(point), 5, (0, 255, 255), -1)
        cv2.line(rendered, tuple(index_mid), tuple(pinky_mid), (0, 255, 255), 2)
        cv2.line(rendered, tuple(index_mcp), tuple(pinky_mcp), (255, 200, 0), 2)

    shoulder = _pose_point(result, int(PoseLandmark.RIGHT_SHOULDER), width, height)
    elbow = _pose_point(result, int(PoseLandmark.RIGHT_ELBOW), width, height)
    wrist = _pose_point(result, int(PoseLandmark.RIGHT_WRIST), width, height)
    if shoulder is not None and elbow is not None and wrist is not None:
        s, e, w = shoulder.astype(int), elbow.astype(int), wrist.astype(int)
        cv2.line(rendered, tuple(s), tuple(e), (255, 0, 255), 2)
        cv2.line(rendered, tuple(e), tuple(w), (255, 0, 255), 2)
        _draw_angle_arc(rendered, tuple(e), tuple(s), tuple(w), (255, 0, 255))

    left_heel = _pose_point(result, int(PoseLandmark.LEFT_HEEL), width, height)
    right_heel = _pose_point(result, int(PoseLandmark.RIGHT_HEEL), width, height)
    left_ankle = _pose_point(result, int(PoseLandmark.LEFT_ANKLE), width, height)
    right_ankle = _pose_point(result, int(PoseLandmark.RIGHT_ANKLE), width, height)
    left_toe = _pose_point(result, int(PoseLandmark.LEFT_FOOT_INDEX), width, height)
    right_toe = _pose_point(result, int(PoseLandmark.RIGHT_FOOT_INDEX), width, height)
    if all(
        p is not None
        for p in (left_heel, right_heel, left_ankle, right_ankle, left_toe, right_toe)
    ):
        left_contact = _medial_foot_contact(left_heel, left_toe, left_ankle, right_ankle).astype(int)
        right_contact = _medial_foot_contact(right_heel, right_toe, right_ankle, left_ankle).astype(int)
        lh, rh, lt, rt = map(lambda p: p.astype(int), (left_heel, right_heel, left_toe, right_toe))
        cv2.circle(rendered, tuple(left_contact), 6, (0, 200, 255), -1)
        cv2.circle(rendered, tuple(right_contact), 6, (0, 200, 255), -1)
        cv2.line(rendered, tuple(left_contact), tuple(right_contact), (0, 200, 255), 2)
        cv2.line(rendered, tuple(lh), tuple(lt), (0, 255, 0), 2)
        cv2.line(rendered, tuple(rh), tuple(rt), (0, 255, 0), 2)

    left_hip = _pose_point(result, int(PoseLandmark.LEFT_HIP), width, height)
    left_wrist_pose = _pose_point(result, int(PoseLandmark.LEFT_WRIST), width, height)
    if left_hip is not None and left_wrist_pose is not None:
        lh = left_hip.astype(int)
        if result.left_hand_landmarks:
            lw = _hand_point(result.left_hand_landmarks, int(HandLandmark.WRIST), width, height).astype(int)
        else:
            lw = left_wrist_pose.astype(int)
        cv2.line(rendered, tuple(lw), tuple(lh), (200, 200, 0), 2)
        cv2.circle(rendered, tuple(lh), 5, (200, 200, 0), -1)

    lines = [
        f"Fingers joined: diff={metrics['finger_width_diff_ratio']:.2f} ({metrics['fingers_joined_score']:.1f}/10)",
        f"Elbow angle: {metrics['elbow_angle_deg']:.1f} deg ({metrics['elbow_angle_score']:.1f}/10)",
        f"Feet contact: d={metrics['heel_distance_ratio']:.2f} (foot len), angle={metrics['heel_angle_deg']:.1f} deg ({metrics['heels_score']:.1f}/10)",
        f"Left hand attached: {metrics['left_hand_attached_score']:.1f}/10",
        f"Difficulty: {metrics['difficulty']:.1f}/5",
        f"Overall score: {metrics['weighted_score']:.1f}/10",
    ]
    y = 28
    for line in lines:
        cv2.putText(rendered, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(rendered, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1, cv2.LINE_AA)
        y += 24

    return rendered


def _create_image_landmarker(min_confidence: float) -> HolisticLandmarker:
    model_path = ensure_models()
    options = HolisticLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=RunningMode.IMAGE,
        min_face_detection_confidence=min_confidence,
        min_face_landmarks_confidence=min_confidence,
        min_hand_landmarks_confidence=min_confidence,
        min_pose_detection_confidence=min_confidence,
        min_pose_landmarks_confidence=min_confidence,
        output_face_blendshapes=False,
        output_segmentation_mask=False,
    )
    return HolisticLandmarker.create_from_options(options)


def _read_frame_at_index(video_path: Path, frame_index: int) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def analyze_posture_for_frames(
    video_path: Path,
    selected_frames: list[FrameMetrics],
    output_root: Path,
    output_dir: Path,
    min_confidence: float,
    difficulty: float,
    posture_top_n: int = 5,
) -> list[PostureAnalysis]:
    posture_dir = output_root / "posture_annotated_frames"
    posture_dir.mkdir(parents=True, exist_ok=True)

    profile = DifficultyProfile.load(override=difficulty)
    holistic = _create_image_landmarker(min_confidence)
    analyses: list[PostureAnalysis] = []

    try:
        for rank, frame_metric in enumerate(selected_frames[:posture_top_n], start=1):
            frame_bgr = _read_frame_at_index(video_path, frame_metric.frame_index)
            if frame_bgr is None:
                continue

            height, width = frame_bgr.shape[:2]
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            result = holistic.detect(mp_image)
            metrics = analyze_posture(result, width, height, profile)

            annotated = draw_posture_annotations(frame_bgr, result, metrics)
            image_name = f"posture_rank_{rank:02d}_frame_{frame_metric.frame_index:06d}.jpg"
            image_path = posture_dir / image_name
            cv2.imwrite(str(image_path), annotated)

            analyses.append(
                PostureAnalysis(
                    rank=rank,
                    frame_index=frame_metric.frame_index,
                    timestamp_ms=frame_metric.timestamp_ms,
                    output_image_path=str(image_path.relative_to(output_dir)),
                    **metrics,
                )
            )
    finally:
        holistic.close()

    return analyses


def save_posture_results(analyses: list[PostureAnalysis], output_root: Path) -> tuple[Path, Path]:
    rows = [asdict(item) for item in analyses]
    json_path = output_root / "posture_analysis.json"
    csv_path = output_root / "posture_analysis.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")

    return json_path, csv_path
