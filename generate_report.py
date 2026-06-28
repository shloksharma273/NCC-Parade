from __future__ import annotations

import argparse
from pathlib import Path

from drill_report_metadata import ReportMetadata
from knee_peak_detector.report import generate_pdf_report


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
    parser.add_argument("--cadet-name", type=str, default=None, help="Cadet name for the report header.")
    parser.add_argument("--cadet-id", type=str, default=None, help="Cadet ID for the report header.")
    parser.add_argument("--session-id", type=str, default=None, help="Session ID for the report header.")
    parser.add_argument("--attempt-number", type=int, default=1, help="Attempt number for the report header.")
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

    metadata = None
    if any([args.cadet_name, args.cadet_id, args.session_id]):
        metadata = ReportMetadata(
            cadet_name=args.cadet_name or "Unknown Cadet",
            cadet_id=args.cadet_id,
            session_id=args.session_id or "",
            attempt_number=args.attempt_number,
            drill_type="kadam_tal",
        )

    pdf_path = generate_pdf_report(
        results_path=results_path,
        output_path=output_pdf,
        output_dir=args.output_dir,
        metadata=metadata,
    )

    print(f"PDF report generated: {pdf_path}")


if __name__ == "__main__":
    main()
