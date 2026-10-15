from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drill_detection.report_metadata import ReportMetadata


@dataclass
class PipelineConfig:
    """Single source of truth for every hill-march tunable. No magic numbers in logic."""

    input_path: Path
    output_dir: Path
    every_k_frames: int = 1
    min_detection_confidence: float = 0.5
    save_annotated_frames: bool = True
    save_raw_frames: bool = False
    save_montage: bool = True  # tile the detected key frames into one image for quick review

    # --- Key-frame (kick) detection ----------------------------------------------------
    # Key frame = LOCAL MAXIMUM of the kick angle (leg raised highest; see
    # landmarks._kick_angle). Same prominence / min-distance / smoothing machinery as
    # slow_march + kadam_tal.
    smooth_window: int = 5
    min_peak_distance_frames: int = 15            # min frames between two key frames (~one per pace)
    min_peak_prominence_deg: float | None = None  # absolute prominence (deg); None => derive from ratio
    min_peak_prominence_ratio: float = 0.15       # prominence as a fraction of the signal range
    # Peaks lower than this are the ordinary steps between kicks (~30-36 deg on the
    # sample footage; kicks were 45-100 deg), not key frames.
    min_kick_peak_deg: float = 40.0

    # Which vectors define "the leg" for the (informational) inter-leg angle:
    #   "hip_ankle" -> full leg (hip->ankle); the literal angle between the two legs (DEFAULT).
    #   "hip_knee"  -> thigh only (hip->knee); more stable when an ankle is occluded / blurred.
    inter_leg_vector: str = "hip_ankle"

    # --- Scoring targets (bands live in scoring.py; single source of truth here) -------
    #   1. legs_apart  -> kick angle should be MORE than this (score_by_min).
    #   2. arms        -> elbow ~180 (straight) AND small shoulder abduction (close to body).
    #                     FRONT view scores only "close to body": a straight arm swung
    #                     toward the camera looks bent in 2D, so elbows can't be judged.
    #   3. legs_straight -> both knees ~180.
    #   4. head_straight -> upright (small tilt) + facing front (small yaw).
    # Parameter 1 is the same in both views: the kick angle comes from vertical ankle
    # lift, which the camera direction does not foreshorten. Full marks at/above
    # kick_full_deg, ramping linearly down to 0 at kick_zero_deg (an ordinary step).
    # PROVISIONAL: set from two sample videos (clean kicks 61-82 deg front, 61-100 side).
    kick_full_deg: float = 60.0
    kick_zero_deg: float = 30.0
    target_arm_angle_deg: float = 180.0    # elbow straight
    target_arm_close_deg: float = 0.0      # shoulder abduction toward torso (0 == arm alongside body)
    target_knee_angle_deg: float = 180.0   # knee straight
    target_head_tilt_deg: float = 0.0      # head upright

    # --- Difficulty knob 0..5 ----------------------------------------------------------
    difficulty: float = 2.0

    # --- Camera view: "front" (default) or "side". The four parameters and the
    #     leg-separation key-frame signal are measured the same way in either view. -----
    view: str = "front"

    # --- Cadet crop: feed MediaPipe a padded box around the cadet instead of the
    #     full frame (see drill_detection/cadet_crop.py). Padding is a fraction of
    #     the body height added on every side. ------------------------------------
    crop_to_cadet: bool = False  # off until validated on more footage
    crop_padding: float = 0.25

    report_metadata: ReportMetadata | None = None
