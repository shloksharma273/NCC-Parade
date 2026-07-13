from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HolisticLandmarker,
    HolisticLandmarkerOptions,
    RunningMode,
)

from . import config as cfg
from .difficulty import scaled_tolerances
from .geometry import to_pixel
from .mediapipe_models import ensure_models
from .scoring import score_by_max

# --- MediaPipe HandLandmark indices (§5.2). Integer constants keep the
#     package self-contained and robust to enum-name changes. ---------------
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

# (mcp, tip) index pairs for the four fingers used by the fist score (§6.5).
_FINGERS = (
    (INDEX_MCP, INDEX_TIP),
    (MIDDLE_MCP, MIDDLE_TIP),
    (RING_MCP, RING_TIP),
    (PINKY_MCP, PINKY_TIP),
)


@dataclass
class HandScore:
    frame_index: int
    fist_score: float
    thumb_score: float
    hands_detected: int
    # Fingertip pixel coords (per detected hand) for optional annotation.
    fingertips_px: list[tuple[float, float]] = field(default_factory=list)


def _hand_point(hand_landmarks, index: int, width: int, height: int) -> np.ndarray:
    return to_pixel(hand_landmarks[index], width, height)


def _hand_scale(hand_landmarks, width: int, height: int) -> float:
    # Hand scale = |WRIST - MIDDLE_MCP|, clamped >= 1.0 (reuse salute::_hand_scale).
    wrist = _hand_point(hand_landmarks, WRIST, width, height)
    middle_mcp = _hand_point(hand_landmarks, MIDDLE_MCP, width, height)
    return max(float(np.linalg.norm(wrist - middle_mcp)), 1.0)


def _fist_score_for_hand(hand_landmarks, width: int, height: int, perfect: float, fail: float) -> float:
    # Per finger F: curl_ratio_F = |TIP_F - WRIST| / |MCP_F - WRIST|.
    # A closed finger folds toward the wrist => small ratio. fist = mean over
    # the four fingers of score_by_max(curl_ratio_F, perfect, fail).  (§6.5)
    wrist = _hand_point(hand_landmarks, WRIST, width, height)
    scores: list[float] = []
    for mcp_idx, tip_idx in _FINGERS:
        tip = _hand_point(hand_landmarks, tip_idx, width, height)
        mcp = _hand_point(hand_landmarks, mcp_idx, width, height)
        mcp_dist = float(np.linalg.norm(mcp - wrist))
        if mcp_dist <= 1e-6:
            scores.append(0.0)
            continue
        curl_ratio = float(np.linalg.norm(tip - wrist)) / mcp_dist
        scores.append(score_by_max(curl_ratio, perfect, fail))
    return float(np.mean(scores)) if scores else 0.0


def _thumb_score_for_hand(hand_landmarks, width: int, height: int, perfect: float, fail: float) -> float:
    # thumb_gap = min(|THUMB_TIP - INDEX_PIP|, |THUMB_TIP - MIDDLE_PIP|) / hand_scale
    # Thumb folded over the front of the fingers => small gap. (§6.6)
    scale = _hand_scale(hand_landmarks, width, height)
    thumb_tip = _hand_point(hand_landmarks, THUMB_TIP, width, height)
    index_pip = _hand_point(hand_landmarks, INDEX_PIP, width, height)
    middle_pip = _hand_point(hand_landmarks, MIDDLE_PIP, width, height)
    gap = min(
        float(np.linalg.norm(thumb_tip - index_pip)),
        float(np.linalg.norm(thumb_tip - middle_pip)),
    ) / scale
    return score_by_max(gap, perfect, fail)


def _create_image_landmarker(min_confidence: float) -> HolisticLandmarker:
    # IMAGE-mode Holistic pass for reliable hand landmarks (reuse salute pattern).
    model_path = ensure_models()
    options = HolisticLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=RunningMode.IMAGE,
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


def analyze_hands_for_frames(
    video_path: Path,
    frame_indices: list[int],
    min_confidence: float,
    difficulty: float,
) -> dict[int, HandScore]:
    """Pass 2: re-run Holistic in IMAGE mode on the key frames and score the
    fist closure (§6.5) and thumb-on-top (§6.6) for each. Scores both hands and
    averages them; falls back to the single detected hand (salute pattern);
    missing hand landmarks => that parameter scores 0."""
    # Difficulty-scaled hand-ratio thresholds (all flow through scaled_tolerances).
    fist_perfect, fist_fail = scaled_tolerances(difficulty, *cfg.FIST_CURL_BAND)
    thumb_perfect, thumb_fail = scaled_tolerances(difficulty, *cfg.THUMB_GAP_BAND)

    results: dict[int, HandScore] = {}
    landmarker = _create_image_landmarker(min_confidence)
    try:
        for frame_index in frame_indices:
            frame_bgr = _read_frame_at_index(video_path, frame_index)
            if frame_bgr is None:
                results[frame_index] = HandScore(frame_index, 0.0, 0.0, 0)
                continue

            height, width = frame_bgr.shape[:2]
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            result = landmarker.detect(mp_image)

            hands = []
            if result.left_hand_landmarks:
                hands.append(result.left_hand_landmarks)
            if result.right_hand_landmarks:
                hands.append(result.right_hand_landmarks)

            if not hands:
                # Missing hand landmarks => fist and thumb score 0 (§6.5/§6.6).
                results[frame_index] = HandScore(frame_index, 0.0, 0.0, 0)
                continue

            fist_vals = [_fist_score_for_hand(h, width, height, fist_perfect, fist_fail) for h in hands]
            thumb_vals = [_thumb_score_for_hand(h, width, height, thumb_perfect, thumb_fail) for h in hands]
            fingertips = [
                (float(_hand_point(h, tip, width, height)[0]), float(_hand_point(h, tip, width, height)[1]))
                for h in hands
                for _, tip in _FINGERS
            ]
            results[frame_index] = HandScore(
                frame_index=frame_index,
                fist_score=float(np.mean(fist_vals)),   # average across detected hands
                thumb_score=float(np.mean(thumb_vals)),
                hands_detected=len(hands),
                fingertips_px=fingertips,
            )
    finally:
        landmarker.close()

    return results
