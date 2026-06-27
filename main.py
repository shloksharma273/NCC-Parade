from __future__ import annotations

import argparse
from pathlib import Path

from salute_detector.config import PipelineConfig as SaluteConfig
from salute_detector.difficulty import load_difficulty
from salute_detector.pipeline import run_pipeline as run_salute_pipeline

from knee_peak_detector.config import PipelineConfig as KadamTalConfig
from knee_peak_detector.pipeline import run_pipeline as run_kadam_tal_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run drill analysis pipelines (salute or kadam tal).")
    parser.add_argument(
        "--drill",
        choices=["salute", "kadam_tal"],
        default="kadam_tal",
        help="Drill type to analyze (default: kadam_tal).",
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
        help="MediaPipe min detection confidence.",
    )
    parser.add_argument(
        "--difficulty",
        type=float,
        default=None,
        help="Scoring difficulty 0-5 (overrides .env DIFFICULTY).",
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

    # Salute-specific
    parser.add_argument("--top-n", type=int, default=10, help="Salute: number of candidate frames.")
    parser.add_argument(
        "--temporal-nms-window",
        type=int,
        default=5,
        help="Salute: suppress candidates within N frames.",
    )
    parser.add_argument(
        "--posture-top-n",
        type=int,
        default=5,
        help="Salute: top frames for posture analysis.",
    )
    parser.add_argument(
        "--no-posture-analysis",
        action="store_true",
        help="Salute: disable posture scoring.",
    )

    # Kadam tal-specific
    parser.add_argument("--smooth-window", type=int, default=5, help="Kadam tal: knee lift smoothing window.")
    parser.add_argument(
        "--min-peak-distance",
        type=int,
        default=15,
        help="Kadam tal: minimum frame distance between peaks.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    difficulty = load_difficulty(args.difficulty)

    if args.drill == "salute":
        if args.top_n <= 0 or args.posture_top_n <= 0:
            raise ValueError("--top-n and --posture-top-n must be >= 1")
        config = SaluteConfig(
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
        summaries = run_salute_pipeline(config)
        print(f"\nSalute detection completed (difficulty={difficulty:.1f}/5).\n")
        for summary in summaries:
            print(f"Video: {summary['video']}")
            print(f"  Selected frames: {summary['selected_count']}")
            print(f"  JSON: {summary['results_json']}")
            if summary.get("posture_analysis_json"):
                print(f"  Posture JSON: {summary['posture_analysis_json']}")
            print()
        return

    if args.smooth_window <= 0 or args.min_peak_distance <= 0:
        raise ValueError("--smooth-window and --min-peak-distance must be >= 1")
    config = KadamTalConfig(
        input_path=args.input,
        output_dir=args.output_dir,
        every_k_frames=args.every_k_frames,
        min_detection_confidence=args.min_detection_confidence,
        save_annotated_frames=not args.no_annotated,
        save_raw_frames=args.save_raw_frames,
        smooth_window=args.smooth_window,
        min_peak_distance_frames=args.min_peak_distance,
        difficulty=difficulty,
    )
    summaries = run_kadam_tal_pipeline(config)
    print(f"\nKadam tal analysis completed (difficulty={difficulty:.1f}/5).\n")
    for summary in summaries:
        print(f"Video: {summary['video']}")
        print(f"  Peak frames: {summary['peak_count']}")
        print(f"  Total score: {summary['total_score']}")
        print(f"  JSON: {summary['results_json']}")
        if summary.get("report_pdf"):
            print(f"  PDF: {summary['report_pdf']}")
        print()


if __name__ == "__main__":
    main()
