from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drill_detection.report_metadata import ReportMetadata


@dataclass
class PipelineConfig:
    """Single source of truth for every slow-march tunable. No magic numbers in logic."""

    input_path: Path
    output_dir: Path
    every_k_frames: int = 1
    min_detection_confidence: float = 0.5
    save_annotated_frames: bool = True
    save_raw_frames: bool = False

    # --- Key-frame (step-extreme) detection on the inter-leg-angle signal ---
    smooth_window: int = 5
    min_peak_distance_frames: int = 15
    min_peak_prominence_deg: float | None = None  # absolute prominence in degrees; None => derive from ratio
    min_peak_prominence_ratio: float = 0.15  # fraction of signal range used when prominence not given

    # --- Scoring targets (see MATH.md / scoring.py) ---
    target_arm_angle_deg: float = 180.0        # arms straight: elbow ~180 deg
    target_grounded_knee_deg: float = 180.0    # grounded leg straight: knee ~180 deg
    target_grounded_vertical_deg: float = 0.0  # grounded leg perpendicular: 0 deg off vertical
    target_head_yaw_deg: float = 0.0           # look front: yaw ratio ~0 (see scoring, uses ratio not deg)
    target_foot_horizontal_deg: float = 0.0    # raised foot flat: 0 deg off horizontal

    # --- Mandatory raised-foot gate (PRD 6.5) ---
    raised_foot_is_mandatory: bool = True
    raised_foot_pass_threshold: float = 5.0  # raised_foot sub-score below this triggers the gate
    raised_foot_gate_cap: float = 4.0        # frame_total capped to this value when the gate fires

    # --- Difficulty knob 0..5 ---
    difficulty: float = 2.0

    # --- Camera view: "side" (default) or "front" (PRD clarified decision) ---
    # 3 of 4 scored params (raised-foot parallel, grounded-leg perpendicular, inter-leg
    # split) are most reliable from the side; head-yaw ("look front") degrades gracefully
    # in side view and is down-weighted there (see scoring.py head_front handling).
    view: str = "side"

    report_metadata: ReportMetadata | None = None
