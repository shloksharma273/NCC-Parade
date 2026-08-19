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

    # --- Difficulty knob 0..5 (reserved for the scoring follow-up) ---------------------
    difficulty: float = 2.0

    # --- Camera view: quick march is filmed front-on in the samples --------------------
    view: str = "front"

    report_metadata: ReportMetadata | None = None
