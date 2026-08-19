from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drill_detection.report_metadata import ReportMetadata


@dataclass
class PipelineConfig:
    """Single source of truth for every tez-chal tunable. No magic numbers in logic."""

    input_path: Path
    output_dir: Path
    every_k_frames: int = 1
    min_detection_confidence: float = 0.5
    save_annotated_frames: bool = True
    save_raw_frames: bool = False
    save_montage: bool = True  # tile the detected key frames into one image for quick review

    # --- Key-frame (step-extreme) detection --------------------------------------------
    # Key frame = LOCAL MAXIMUM of the inter-leg angle (legs maximally split). Same
    # prominence / min-distance / smoothing machinery as slow_march + kadam_tal.
    smooth_window: int = 5
    min_peak_distance_frames: int = 15            # min frames between two key frames (~one per pace)
    min_peak_prominence_deg: float | None = None  # absolute prominence (deg); None => derive from ratio
    min_peak_prominence_ratio: float = 0.15       # prominence as a fraction of the signal range

    # Which vectors define "the leg" for the inter-leg angle:
    #   "hip_ankle" -> full leg (hip->ankle); the literal angle between the two legs (DEFAULT).
    #   "hip_knee"  -> thigh only (hip->knee); more stable when an ankle is occluded / blurred
    #                  at the top of a fast knee-lift. Selectable for A/B.
    inter_leg_vector: str = "hip_ankle"

    # --- Scoring (see scoring.py). Three parameters, each ideal held ALWAYS; the
    #     score falls off proportionally as the pose deviates from the ideal:
    #       1. arms_straight  -> both elbows ~180 deg
    #       2. legs_straight  -> both knees  ~180 deg
    #       3. fist_closed    -> fingers curled toward the wrist (hand landmarks)
    # Bands live in scoring.py; targets/weights are here (single source of truth).
    target_arm_angle_deg: float = 180.0    # elbow straight
    target_knee_angle_deg: float = 180.0   # knee straight
    hand_min_confidence: float = 0.3       # confidence for the IMAGE-mode hand pass
    # Fist-closed snap window: at the step extreme the arms swing fastest, so the hands
    # are motion-blurred and often undetectable ON the key frame itself. Because the fist
    # must be closed ALWAYS, we evaluate it on the SHARPEST nearby frames instead: sample
    # frames within +/- hand_snap_window (every hand_snap_step frames) and average the fist
    # score over those where a hand is actually detected. Set hand_snap_window=0 to score
    # strictly on the key frame.
    hand_snap_window: int = 8
    hand_snap_step: int = 2

    # --- Difficulty knob 0..5 ----------------------------------------------------------
    difficulty: float = 2.0

    # --- Camera view: quick march is filmed front-on in the samples --------------------
    view: str = "front"

    report_metadata: ReportMetadata | None = None
