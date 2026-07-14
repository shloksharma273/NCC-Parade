from __future__ import annotations

import argparse
from pathlib import Path

from drill_detection.salute.config import PipelineConfig as SaluteConfig
from drill_detection.salute.difficulty import load_difficulty
from drill_detection.salute.pipeline import run_pipeline as run_salute_pipeline

from drill_detection.kadam_tal.config import PipelineConfig as KadamTalConfig
from drill_detection.kadam_tal.pipeline import run_pipeline as run_kadam_tal_pipeline

from drill_detection.baju_swing.config import PipelineConfig as BajuSwingConfig
from drill_detection.baju_swing.pipeline import run_pipeline as run_baju_swing_pipeline

from drill_detection.slow_march.config import PipelineConfig as SlowMarchConfig
from drill_detection.slow_march.pipeline import run_pipeline as run_slow_march_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run drill analysis pipelines (salute, kadam tal, baju swing, or slow march)."
    )
    parser.add_argument(
        "--drill",
        choices=["salute", "kadam_tal", "baju_swing", "slow_march"],
        default="kadam_tal",
        help="Drill type to analyze (default: kadam_tal).",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("test_data/dataset"),
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

    # Shared signal smoothing / peak spacing (kadam tal, slow march, baju swing)
    parser.add_argument("--smooth-window", type=int, default=5, help="Kadam tal / slow march: signal smoothing window.")
    parser.add_argument(
        "--min-peak-distance",
        type=int,
        default=15,
        help="Kadam tal / slow march: minimum frame distance between peaks.",
    )

    # Camera view, shared by slow march and baju swing (default: side)
    parser.add_argument(
        "--view",
        choices=["front", "side"],
        default="side",
        help="Slow march / baju swing: camera view (default: side).",
    )
    parser.add_argument(
        "--key-frame-signal",
        choices=["auto", "foot_passing", "stride", "perpendicular_hind", "merged", "inter_leg_angle"],
        default="auto",
        help=(
            "Slow march: key-frame detector. 'auto' (default) uses the ACTIVE foot-passing "
            "detector (both feet flat + legs together) for side view; 'stride' / "
            "'perpendicular_hind' / 'merged' are the earlier stride-based detectors; "
            "'inter_leg_angle' is the front-view fallback."
        ),
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

    if args.drill == "baju_swing":
        config = BajuSwingConfig(
            input_path=args.input,
            output_dir=args.output_dir,
            view=args.view,
            every_k_frames=args.every_k_frames,
            min_detection_confidence=args.min_detection_confidence,
            save_annotated_frames=not args.no_annotated,
            save_raw_frames=args.save_raw_frames,
            smooth_window=args.smooth_window,
            min_peak_distance_frames=args.min_peak_distance,
            difficulty=difficulty,
        )
        summaries = run_baju_swing_pipeline(config)
        print(f"\nBaju swing analysis completed (view={args.view}, difficulty={difficulty:.1f}/5).\n")
        for summary in summaries:
            print(f"Video: {summary['video']}")
            print(f"  Swings (iterations): {summary['iteration_count']}")
            print(f"  Total score: {summary['total_score']}")
            print(f"  Average score/swing: {summary['average_score']}")
            print(f"  JSON: {summary['results_json']}")
            if summary.get("report_pdf"):
                print(f"  PDF: {summary['report_pdf']}")
            print()
        return

    if args.drill == "slow_march":
        config = SlowMarchConfig(
            input_path=args.input,
            output_dir=args.output_dir,
            every_k_frames=args.every_k_frames,
            min_detection_confidence=args.min_detection_confidence,
            save_annotated_frames=not args.no_annotated,
            save_raw_frames=args.save_raw_frames,
            smooth_window=args.smooth_window,
            min_peak_distance_frames=args.min_peak_distance,
            difficulty=difficulty,
            view=args.view,
            key_frame_signal=args.key_frame_signal,
        )
        summaries = run_slow_march_pipeline(config)
        print(
            f"\nSlow march analysis completed "
            f"(difficulty={difficulty:.1f}/5, view={args.view}, key_frame_signal={args.key_frame_signal}).\n"
        )
        for summary in summaries:
            print(f"Video: {summary['video']}")
            print(f"  Steps (iterations): {summary['iteration_count']}")
            print(f"  Total score: {summary['total_score']}")
            print(f"  Average score/step: {summary['average_score']}")
            print(f"  JSON: {summary['results_json']}")
            if summary.get("report_pdf"):
                print(f"  PDF: {summary['report_pdf']}")
            print()
        return

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
