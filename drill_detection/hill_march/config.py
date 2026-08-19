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

    # --- Key-frame (max-leg-separation) detection --------------------------------------
    # Key frame = LOCAL MAXIMUM of the inter-leg angle (legs maximally separated). Same
    # prominence / min-distance / smoothing machinery as slow_march + kadam_tal.
    smooth_window: int = 5
    min_peak_distance_frames: int = 15            # min frames between two key frames (~one per pace)
    min_peak_prominence_deg: float | None = None  # absolute prominence (deg); None => derive from ratio
    min_peak_prominence_ratio: float = 0.15       # prominence as a fraction of the signal range

    # Which vectors define "the leg" for the inter-leg (separation) angle:
    #   "hip_ankle" -> full leg (hip->ankle); the literal angle between the two legs (DEFAULT).
    #   "hip_knee"  -> thigh only (hip->knee); more stable when an ankle is occluded / blurred.
    inter_leg_vector: str = "hip_ankle"

    # --- Scoring targets (bands live in scoring.py; single source of truth here) -------
    #   1. legs_apart  -> inter-leg angle should be MORE than this (score_by_min).
    #   2. arms        -> elbow ~180 (straight) AND small shoulder abduction (close to body).
    #   3. legs_straight -> both knees ~180.
    #   4. head_straight -> upright (small tilt) + facing front (small yaw).
    # Parameter 1 threshold is VIEW-DEPENDENT: the front-on camera foreshortens the
    # forward/back stride, so a smaller separation earns full marks than from the side.
    # Full marks (10) at/above this angle, ramping linearly down to 0 at 0 deg.
    legs_apart_full_deg_front: float = 50.0   # front view: 50 deg => 10, ramp down
    legs_apart_full_deg_side: float = 70.0    # side view:  70 deg => 10, ramp down
    target_arm_angle_deg: float = 180.0    # elbow straight
    target_arm_close_deg: float = 0.0      # shoulder abduction toward torso (0 == arm alongside body)
    target_knee_angle_deg: float = 180.0   # knee straight
    target_head_tilt_deg: float = 0.0      # head upright

    # --- Difficulty knob 0..5 ----------------------------------------------------------
    difficulty: float = 2.0

    # --- Camera view: "front" (default) or "side". The four parameters and the
    #     leg-separation key-frame signal are measured the same way in either view. -----
    view: str = "front"

    report_metadata: ReportMetadata | None = None
