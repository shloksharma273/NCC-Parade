from __future__ import annotations

import argparse
from pathlib import Path

from knee_peak_detector.report import DEFAULT_PERSON_ID, generate_pdf_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a PDF report from kadam tal results.json.")
    parser.add_argument(
        "--results",
        type=Path,
        default=None,
        help="Path to results.json (default: output/<video>/results.json or latest in output/).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Base output directory where frame images are stored.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PDF path (default: alongside results.json as kadam_tal_report.pdf).",
    )
    parser.add_argument(
        "--person-id",
        type=str,
        default=DEFAULT_PERSON_ID,
        help=f"Person identifier shown in the report header (default: {DEFAULT_PERSON_ID}).",
    )
    return parser


def _find_default_results(output_dir: Path) -> Path | None:
    candidates = sorted(output_dir.glob("*/results.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    results_path = args.results
    if results_path is None:
        results_path = _find_default_results(args.output_dir)
        if results_path is None:
            raise RuntimeError(f"No results.json found under {args.output_dir}")

    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")

    output_pdf = args.output
    if output_pdf is None:
        output_pdf = results_path.parent / "kadam_tal_report.pdf"

    pdf_path = generate_pdf_report(
        results_path=results_path,
        output_path=output_pdf,
        output_dir=args.output_dir,
        person_id=args.person_id,
    )

    print(f"PDF report generated: {pdf_path}")


if __name__ == "__main__":
    main()
