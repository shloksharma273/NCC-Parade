from dataclasses import dataclass
from pathlib import Path

from drill_report_metadata import ReportMetadata


@dataclass
class PipelineConfig:
    input_path: Path
    output_dir: Path
    every_k_frames: int = 1
    min_detection_confidence: float = 0.5
    save_annotated_frames: bool = True
    save_raw_frames: bool = False
    smooth_window: int = 5
    min_peak_distance_frames: int = 15
    min_peak_prominence_px: float | None = None
    min_peak_prominence_ratio: float = 0.15
    difficulty: float = 2.0
    report_metadata: ReportMetadata | None = None
