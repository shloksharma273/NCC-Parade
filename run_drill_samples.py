#!/usr/bin/env python3
"""Batch-process the "Drill Samples" folder through the drill detectors.

Reads an input tree shaped like:

    <input>/<drill name>/<front view|side view>/<video>.mp4

runs the matching drill detector on every video, and writes each result into a
mirror tree under a SEPARATE output directory so the input videos folder stays
clean and untouched:

    <output>/<drill name>/<view>/<video stem>/results.json, key frames, report.pdf

Only drills that have a detector are processed (salute, kadam_tal, baju_swing,
slow_march, tez_chal). Unsupported sample folders (hill march, dst drill,
tez march) are listed and skipped. View-aware drills (baju_swing, slow_march) use the view taken
from the folder name; other drills ignore it.

Usage:
    python run_drill_samples.py \
        --input "test_data/Drill Samples" \
        --output "test_data/Drill Sample Results" \
        --difficulty 2
"""
from __future__ import annotations

import argparse
import csv
import json
import traceback
from pathlib import Path

from drill_detection.report_metadata import ReportMetadata

from drill_detection.salute.config import PipelineConfig as SaluteConfig
from drill_detection.salute.pipeline import run_pipeline as run_salute
from drill_detection.kadam_tal.config import PipelineConfig as KadamTalConfig
from drill_detection.kadam_tal.pipeline import run_pipeline as run_kadam_tal
from drill_detection.baju_swing.config import PipelineConfig as BajuSwingConfig
from drill_detection.baju_swing.pipeline import run_pipeline as run_baju_swing
from drill_detection.slow_march.config import PipelineConfig as SlowMarchConfig
from drill_detection.slow_march.pipeline import run_pipeline as run_slow_march
from drill_detection.tez_chal.config import PipelineConfig as TezChalConfig
from drill_detection.tez_chal.pipeline import run_pipeline as run_tez_chal

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}

# Sample folder name (lower-cased, trimmed) -> drill slug. None = recognised drill
# but no detector yet, so it is skipped (not an error).
DRILL_FOLDER_TO_SLUG: dict[str, str | None] = {
    "baju swing": "baju_swing",
    "kadam tal": "kadam_tal",
    "salute": "salute",
    "slow march": "slow_march",
    "tez chal": "tez_chal",
    "hill march": None,
    "dst drill": None,
    "tez march": None,
}

VIEW_AWARE = {"baju_swing", "slow_march"}


def detect_view(parts: tuple[str, ...]) -> str | None:
    """Return 'front'/'side' from any 'front view'/'side view' folder in the path."""
    for part in parts:
        low = part.lower()
        if "front" in low:
            return "front"
        if "side" in low:
            return "side"
    return None


def run_drill(slug: str, video: Path, out_dir: Path, view: str | None,
              difficulty: float, metadata: ReportMetadata) -> list[dict]:
    """Build the drill's PipelineConfig and run it. Output lands in out_dir/<stem>/."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if slug == "salute":
        cfg = SaluteConfig(
            input_path=video, output_dir=out_dir, difficulty=difficulty,
            save_annotated_frames=True, enable_posture_analysis=True, force_posture_analysis=True,
        )
        return run_salute(cfg)
    if slug == "kadam_tal":
        cfg = KadamTalConfig(
            input_path=video, output_dir=out_dir, difficulty=difficulty,
            save_annotated_frames=True, report_metadata=metadata,
        )
        return run_kadam_tal(cfg)
    if slug == "baju_swing":
        cfg = BajuSwingConfig(
            input_path=video, output_dir=out_dir, difficulty=difficulty,
            view=view or "side", save_annotated_frames=True, report_metadata=metadata,
        )
        return run_baju_swing(cfg)
    if slug == "slow_march":
        cfg = SlowMarchConfig(
            input_path=video, output_dir=out_dir, difficulty=difficulty,
            view=view or "side", save_annotated_frames=True, report_metadata=metadata,
        )
        return run_slow_march(cfg)
    if slug == "tez_chal":
        cfg = TezChalConfig(
            input_path=video, output_dir=out_dir, difficulty=difficulty,
            save_annotated_frames=True, report_metadata=metadata,
        )
        return run_tez_chal(cfg)
    raise ValueError(f"No detector for slug '{slug}'")


def summarise(summaries: list[dict]) -> dict:
    """Normalise a drill's per-video summary into common fields (drills differ)."""
    s = summaries[0] if summaries else {}
    reps = s.get("iteration_count", s.get("peak_count", s.get("selected_count")))
    avg = s.get("average_score", s.get("average_score_per_swing", s.get("average_score_per_step")))
    return {
        "reps": reps,
        "total_score": s.get("total_score"),
        "average_score": avg,
        "results_json": s.get("results_json"),
        "report_pdf": s.get("report_pdf"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-run drill detectors over a Drill Samples tree.")
    parser.add_argument("--input", type=Path, default=Path("test_data/Drill Samples"),
                        help="Input samples root (default: test_data/Drill Samples).")
    parser.add_argument("--output", type=Path, default=Path("test_data/Drill Sample Results"),
                        help="Output root; mirrors the input tree (default: test_data/Drill Sample Results).")
    parser.add_argument("--difficulty", type=float, default=2.0, help="Scoring difficulty 0-5 (default 2).")
    args = parser.parse_args()

    input_root: Path = args.input
    output_root: Path = args.output
    if not input_root.is_dir():
        raise SystemExit(f"Input folder not found: {input_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    videos = sorted(p for p in input_root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    print(f"Found {len(videos)} video(s) under {input_root}\n")

    records: list[dict] = []
    for video in videos:
        rel = video.relative_to(input_root)
        drill_folder = rel.parts[0]
        slug = DRILL_FOLDER_TO_SLUG.get(drill_folder.strip().lower(), "UNKNOWN")
        view = detect_view(rel.parts[1:-1]) if slug in VIEW_AWARE else None
        record = {
            "video": str(rel), "drill_folder": drill_folder, "drill": slug,
            "view": view, "status": "", "reps": None, "total_score": None,
            "average_score": None, "results_json": None, "report_pdf": None, "error": None,
        }

        if slug == "UNKNOWN":
            record["status"] = "skipped (unrecognised drill folder)"
            print(f"[SKIP] {rel}  — unknown drill folder '{drill_folder}'")
        elif slug is None:
            record["status"] = "skipped (no detector for this drill yet)"
            print(f"[SKIP] {rel}  — '{drill_folder}' has no detector yet")
        else:
            # Mirror the input structure: <output>/<drill folder>/<view folder>/
            out_dir = output_root / rel.parent
            metadata = ReportMetadata(
                cadet_name=f"{drill_folder} sample", drill_type=slug, session_id=video.stem,
            )
            label = f"{slug}" + (f" [{view}]" if view else "")
            print(f"[RUN ] {rel}  — {label} ...", flush=True)
            try:
                summaries = run_drill(slug, video, out_dir, view, args.difficulty, metadata)
                record.update(summarise(summaries))
                record["status"] = "ok"
                print(f"        -> reps={record['reps']} avg={record['average_score']} "
                      f"json={record['results_json']}")
            except Exception as exc:  # keep going on failures
                record["status"] = "error"
                record["error"] = str(exc) or exc.__class__.__name__
                print(f"        !! ERROR: {record['error']}")
                traceback.print_exc()
        records.append(record)

    # Write a batch-level index next to the results.
    (output_root / "_summary.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    with (output_root / "_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()) if records else [])
        writer.writeheader()
        writer.writerows(records)

    ok = sum(1 for r in records if r["status"] == "ok")
    skipped = sum(1 for r in records if r["status"].startswith("skipped"))
    errors = sum(1 for r in records if r["status"] == "error")
    print(f"\nDone. {ok} processed, {skipped} skipped, {errors} error(s).")
    print(f"Results + _summary.json/_summary.csv written to: {output_root}")


if __name__ == "__main__":
    main()
