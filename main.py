from __future__ import annotations

import argparse
from pathlib import Path

from knee_peak_detector.config import PipelineConfig
from knee_peak_detector.difficulty import load_difficulty
from knee_peak_detector.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect knee peak frames, score posture, and count kadam tal."
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
        help="MediaPipe min pose detection confidence.",
    )
    parser.add_argument(
        "--smooth-window",
        type=int,
        default=5,
        help="Moving-average window for knee lift signal smoothing.",
    )
    parser.add_argument(
        "--min-peak-distance",
        type=int,
        default=15,
        help="Minimum frame distance between detected knee peaks.",
    )
    parser.add_argument(
        "--min-peak-prominence",
        type=float,
        default=None,
        help="Minimum peak prominence in pixels (auto if omitted).",
    )
    parser.add_argument(
        "--min-peak-prominence-ratio",
        type=float,
        default=0.15,
        help="Auto prominence as a fraction of lift range when prominence px is omitted.",
    )
    parser.add_argument(
        "--difficulty",
        type=float,
        default=None,
        help="Scoring difficulty 0-5 (overrides .env DIFFICULTY). 0=lenient, 5=strict.",
    )
    parser.add_argument(
        "--save-raw-frames",
        action="store_true",
        help="Save raw peak frames in addition to annotated frames.",
    )
    parser.add_argument(
        "--no-annotated",
        action="store_true",
        help="Disable saving annotated frames.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.every_k_frames <= 0:
        raise ValueError("--every-k-frames must be >= 1")
    if args.smooth_window <= 0:
        raise ValueError("--smooth-window must be >= 1")
    if args.min_peak_distance <= 0:
        raise ValueError("--min-peak-distance must be >= 1")
    if not (0.0 <= args.min_detection_confidence <= 1.0):
        raise ValueError("--min-detection-confidence must be between 0 and 1")

    difficulty = load_difficulty(args.difficulty)

    config = PipelineConfig(
        input_path=args.input,
        output_dir=args.output_dir,
        every_k_frames=args.every_k_frames,
        min_detection_confidence=args.min_detection_confidence,
        save_annotated_frames=not args.no_annotated,
        save_raw_frames=args.save_raw_frames,
        smooth_window=args.smooth_window,
        min_peak_distance_frames=args.min_peak_distance,
        min_peak_prominence_px=args.min_peak_prominence,
        min_peak_prominence_ratio=args.min_peak_prominence_ratio,
        difficulty=difficulty,
    )

    summaries = run_pipeline(config)
    print(f"\nKnee peak scoring completed (difficulty={difficulty:.1f}/5).\n")
    for summary in summaries:
        print(f"Video: {summary['video']}")
        print(f"  Processed frames: {summary['processed_frames']}")
        print(f"  Valid scored frames: {summary['valid_scored_frames']}")
        print(f"  Kadam tal count: {summary['kadam_tal_count']}")
        print(f"  Total score: {summary['total_score']}/{summary['kadam_tal_count'] * 10}")
        print(f"  Average score per kadam tal: {summary['average_score']:.2f}/10")
        print(f"  JSON: {summary['results_json']}")
        if summary.get("report_pdf"):
            print(f"  PDF: {summary['report_pdf']}")
        print()


if __name__ == "__main__":
    main()
