from __future__ import annotations

import argparse
from pathlib import Path

from salute_detector.config import PipelineConfig
from salute_detector.difficulty import load_difficulty
from salute_detector.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect salute candidate frames using right forefinger to eyebrow distance."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data"),
        help="Input video file or directory (default: data).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory for results and frames.",
    )
    parser.add_argument("--top-n", type=int, default=10, help="Number of candidate frames to return per video.")
    parser.add_argument(
        "--every-k-frames",
        type=int,
        default=1,
        help="Process one frame every K frames.",
    )
    parser.add_argument(
        "--min-detection-confidence",
        type=float,
        default=0.5,
        help="MediaPipe min detection/tracking confidence.",
    )
    parser.add_argument(
        "--temporal-nms-window",
        type=int,
        default=5,
        help="Suppress candidates within N frames of stronger candidates.",
    )
    parser.add_argument(
        "--save-raw-frames",
        action="store_true",
        help="Save raw selected frames in addition to annotated frames.",
    )
    parser.add_argument(
        "--no-annotated",
        action="store_true",
        help="Disable saving annotated frames.",
    )
    parser.add_argument(
        "--posture-top-n",
        type=int,
        default=5,
        help="Number of top front-salute frames to run posture checks on.",
    )
    parser.add_argument(
        "--no-posture-analysis",
        action="store_true",
        help="Disable posture scoring for front-facing salute videos.",
    )
    parser.add_argument(
        "--difficulty",
        type=float,
        default=None,
        help="Drill difficulty 0-5 (overrides .env DIFFICULTY). 0=lenient, 5=strict.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.every_k_frames <= 0:
        raise ValueError("--every-k-frames must be >= 1")
    if args.top_n <= 0:
        raise ValueError("--top-n must be >= 1")
    if args.posture_top_n <= 0:
        raise ValueError("--posture-top-n must be >= 1")
    if not (0.0 <= args.min_detection_confidence <= 1.0):
        raise ValueError("--min-detection-confidence must be between 0 and 1")

    difficulty = load_difficulty(args.difficulty)

    config = PipelineConfig(
        input_path=args.input,
        output_dir=args.output_dir,
        top_n=args.top_n,
        every_k_frames=args.every_k_frames,
        min_detection_confidence=args.min_detection_confidence,
        save_annotated_frames=not args.no_annotated,
        save_raw_frames=args.save_raw_frames,
        temporal_nms_window=args.temporal_nms_window,
        posture_top_n=args.posture_top_n,
        enable_posture_analysis=not args.no_posture_analysis,
        difficulty=difficulty,
    )

    summaries = run_pipeline(config)
    print(f"\nSalute detection completed (difficulty={difficulty:.1f}/5).\n")
    for summary in summaries:
        print(f"Video: {summary['video']}")
        print(f"  Processed frames: {summary['processed_frames']}")
        print(f"  Valid scored frames: {summary['valid_scored_frames']}")
        print(f"  Selected frames: {summary['selected_count']}")
        print(f"  JSON: {summary['results_json']}")
        print(f"  CSV: {summary['results_csv']}")
        if summary.get("posture_analysis_csv"):
            print(f"  Posture JSON: {summary['posture_analysis_json']}")
            print(f"  Posture CSV: {summary['posture_analysis_csv']}")
        print()


if __name__ == "__main__":
    main()

