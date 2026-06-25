from __future__ import annotations

import argparse
from pathlib import Path

from salute_detector.difficulty import load_difficulty
from salute_detector.image_scoring import score_images_in_folder, seed_test_images

DEFAULT_TEST_IMAGES_DIR = Path("data/test_images")
DEFAULT_SEED_SOURCE = Path("output/front_salute/annotated_frames")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score static salute images for accuracy testing.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_TEST_IMAGES_DIR,
        help="Folder containing salute images to score.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/image_scores"),
        help="Output folder for annotated images and per-image JSON.",
    )
    parser.add_argument(
        "--difficulty",
        type=float,
        default=None,
        help="Drill difficulty 0-5 (overrides .env DIFFICULTY).",
    )
    parser.add_argument(
        "--min-detection-confidence",
        type=float,
        default=0.5,
        help="MediaPipe min detection confidence.",
    )
    parser.add_argument(
        "--seed-from",
        type=Path,
        default=None,
        help="Optional folder to copy seed images into --input-dir when it is empty.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not (0.0 <= args.min_detection_confidence <= 1.0):
        raise ValueError("--min-detection-confidence must be between 0 and 1")

    input_dir = args.input_dir
    input_dir.mkdir(parents=True, exist_ok=True)

    if not any(input_dir.iterdir()):
        seed_source = args.seed_from or DEFAULT_SEED_SOURCE
        if seed_source.exists():
            copied = seed_test_images(seed_source, input_dir)
            print(f"Seeded {copied} image(s) from {seed_source} into {input_dir}")

    difficulty = load_difficulty(args.difficulty)
    results = score_images_in_folder(
        input_dir=input_dir,
        output_dir=args.output_dir,
        difficulty=difficulty,
        min_confidence=args.min_detection_confidence,
    )

    print(f"\nImage scoring completed (difficulty={difficulty:.1f}/5).\n")
    print(f"Scored images: {len(results)}")
    print(f"Annotated output: {args.output_dir / 'annotated'}")
    print(f"Per-image JSON: {args.output_dir / 'results'}")
    print(f"Summary JSON: {args.output_dir / 'summary.json'}\n")

    for item in results:
        print(f"{item.image_id}: total={item.payload['total_score']}/10")
        print(f"  JSON: {item.result_json}")
        print(f"  Image: {item.annotated_image}")


if __name__ == "__main__":
    main()
