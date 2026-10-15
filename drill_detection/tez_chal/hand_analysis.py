from __future__ import annotations

from dataclasses import dataclass
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

from ..cadet_crop import CropBox, nearest_box, place_on_canvas, uncrop_result
from .difficulty import scaled_tolerances
from .mediapipe_models import ensure_models
from .scoring import FIST_CURL_BAND, score_by_max

# --- MediaPipe HandLandmark indices. Integer constants keep the package
#     self-contained and robust to enum-name changes (same set as baju_swing). ---
WRIST = 0
INDEX_MCP = 5
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_TIP = 12
RING_MCP = 13
RING_TIP = 16
PINKY_MCP = 17
PINKY_TIP = 20

# (mcp, tip) index pairs for the four fingers used by the fist-closed score.
_FINGERS = (
    (INDEX_MCP, INDEX_TIP),
    (MIDDLE_MCP, MIDDLE_TIP),
    (RING_MCP, RING_TIP),
    (PINKY_MCP, PINKY_TIP),
)


# Why a key frame's fist could not be assessed (HandScore.not_assessed_reason).
NO_HAND = "no_hand"                # no hand found in any sampled frame
HAND_TOO_SMALL = "hand_too_small"  # hands found, but all too small for finger geometry


@dataclass
class HandScore:
    frame_index: int
    # /10; 10 == fully closed fist. None == not assessed (see not_assessed_reason):
    # the camera could not see the hand well enough, which must not cost the cadet marks.
    fist_score: float | None
    hands_detected: int      # max hands found across the snap window (0 / 1 / 2)
    samples_with_hands: int = 0  # how many sampled frames had a hand big enough to score
    samples_total: int = 0       # how many frames were sampled around the key frame
    not_assessed_reason: str | None = None


def _hand_point(hand_landmarks, index: int, width: int, height: int) -> np.ndarray:
    lm = hand_landmarks[index]
    return np.array([float(lm.x * width), float(lm.y * height)])


def _hand_size_px(hand_landmarks, width: int, height: int) -> float:
    """Wrist -> middle-finger knuckle distance in full-frame pixels."""
    return float(np.linalg.norm(
        _hand_point(hand_landmarks, MIDDLE_MCP, width, height) - _hand_point(hand_landmarks, WRIST, width, height)
    ))


def _fist_score_for_hand(hand_landmarks, width: int, height: int, perfect: float, fail: float) -> float:
    # Per finger F: curl_ratio_F = |TIP_F - WRIST| / |MCP_F - WRIST|.
    # A closed finger folds toward the wrist => small ratio. fist = mean over the
    # four fingers of score_by_max(curl_ratio_F, perfect, fail). (baju_swing §6.5)
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


def _create_image_landmarker(min_confidence: float) -> HolisticLandmarker:
    # IMAGE-mode Holistic pass for reliable hand landmarks (baju_swing / salute pattern).
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


def _fist_for_single_frame(
    landmarker: HolisticLandmarker,
    video_path: Path,
    frame_index: int,
    perfect: float,
    fail: float,
    cadet_boxes: dict[int, CropBox] | None = None,
    min_hand_size_px: float = 0.0,
) -> tuple[float, int, int]:
    """(mean fist score over hands big enough to score, hands_detected, hands_scored)
    for ONE frame. The score is nan when no hand is found or every hand found is
    smaller than ``min_hand_size_px``."""
    frame_bgr = _read_frame_at_index(video_path, frame_index)
    if frame_bgr is None:
        return float("nan"), 0, 0
    height, width = frame_bgr.shape[:2]
    # Crop to the cadet's box from the pose pass (nearest frame that had one);
    # landmarks are mapped back so the fist maths stays in full-frame pixels.
    # Frame-sized canvas: one landmarker must always see the same image size.
    box = (nearest_box(cadet_boxes, frame_index) if cadet_boxes else None) or CropBox.full(width, height)
    view = place_on_canvas(frame_bgr, box, canvas=(width, height))
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(view.image, cv2.COLOR_BGR2RGB))
    result = uncrop_result(landmarker.detect(mp_image), view)
    hands = [h for h in (result.left_hand_landmarks or None, result.right_hand_landmarks or None) if h]
    if not hands:
        return float("nan"), 0, 0
    scorable = [h for h in hands if _hand_size_px(h, width, height) >= min_hand_size_px]
    if not scorable:
        return float("nan"), len(hands), 0
    fist_vals = [_fist_score_for_hand(h, width, height, perfect, fail) for h in scorable]
    return float(np.mean(fist_vals)), len(hands), len(scorable)


def analyze_hands_for_frames(
    video_path: Path,
    frame_indices: list[int],
    min_confidence: float,
    difficulty: float,
    snap_window: int = 0,
    snap_step: int = 1,
    frame_count: int | None = None,
    cadet_boxes: dict[int, CropBox] | None = None,
    min_hand_size_px: float = 0.0,
) -> dict[int, HandScore]:
    """Pass 2: re-run Holistic in IMAGE mode near each key frame and score the
    fist-closed parameter.

    At the step extreme the arms swing fastest, so the hands are motion-blurred and
    frequently undetectable on the key frame itself. Because the fist must be closed
    ALWAYS, we sample frames within +/- snap_window (every snap_step frames) and average
    the fist score over the frames where a hand is actually detected. snap_window=0
    scores strictly on the key frame.

    Hands smaller than ``min_hand_size_px`` (wrist -> middle knuckle) are ignored:
    the finger landmarks are guesswork at that size. When no sampled frame has a
    hand big enough, the fist is NOT ASSESSED (fist_score None) rather than 0.
    """
    fist_perfect, fist_fail = scaled_tolerances(difficulty, *FIST_CURL_BAND)

    results: dict[int, HandScore] = {}
    landmarker = _create_image_landmarker(min_confidence)
    try:
        for frame_index in frame_indices:
            # Frames to sample around the key frame (deduped, clamped to >= 0 / < frame_count).
            offsets = range(-snap_window, snap_window + 1, max(1, snap_step))
            sample_idxs = sorted({max(0, frame_index + off) for off in offsets})
            if frame_count is not None:
                sample_idxs = [i for i in sample_idxs if i < frame_count]

            fist_vals: list[float] = []
            max_hands = 0
            for idx in sample_idxs:
                fist, hands, scored = _fist_for_single_frame(
                    landmarker, video_path, idx, fist_perfect, fist_fail, cadet_boxes, min_hand_size_px
                )
                max_hands = max(max_hands, hands)
                if scored > 0:
                    fist_vals.append(fist)

            reason = None
            if not fist_vals:
                reason = HAND_TOO_SMALL if max_hands > 0 else NO_HAND
            results[frame_index] = HandScore(
                frame_index=frame_index,
                fist_score=float(np.mean(fist_vals)) if fist_vals else None,
                hands_detected=max_hands,
                samples_with_hands=len(fist_vals),
                samples_total=len(sample_idxs),
                not_assessed_reason=reason,
            )
    finally:
        landmarker.close()

    return results
