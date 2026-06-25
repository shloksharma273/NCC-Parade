from dataclasses import dataclass
from pathlib import Path


@dataclass
class PipelineConfig:
    input_path: Path
    output_dir: Path
    top_n: int = 10
    every_k_frames: int = 1
    min_detection_confidence: float = 0.5
    save_annotated_frames: bool = True
    save_raw_frames: bool = False
    temporal_nms_window: int = 5
    posture_top_n: int = 5
    enable_posture_analysis: bool = True
    difficulty: float = 2.0

