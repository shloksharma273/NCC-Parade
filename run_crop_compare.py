#!/usr/bin/env python3
"""Run the hill_march / tez_chal test videos with and without cadet cropping.

Each run writes one folder per video (results.json, key frames, montage, PDF)
under ``<output>/<label>/`` plus a ``_summary.json`` for that label. Run once
with ``--no-crop`` and once with ``--crop``, then ``--compare`` to diff them.

Usage:
    python run_crop_compare.py --label baseline --no-crop
    python run_crop_compare.py --label cropped  --crop
    python run_crop_compare.py --compare baseline cropped
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import fields
from pathlib import Path

from drill_detection.hill_march.config import PipelineConfig as HillMarchConfig
from drill_detection.hill_march.pipeline import run_pipeline as run_hill_march
from drill_detection.report_metadata import ReportMetadata
from drill_detection.tez_chal.config import PipelineConfig as TezChalConfig
from drill_detection.tez_chal.pipeline import run_pipeline as run_tez_chal

OUTPUT_ROOT = Path("test_data/crop_comparison")

# (video, drill, view)
VIDEOS = [
    (Path("test_data/hill_march_fw_1.mp4"), "hill_march", "front"),
    (Path("test_data/hill_march_sw.mp4"), "hill_march", "side"),
    (Path("test_data/Tez chal side v.mp4"), "tez_chal", "side"),
]

DRILLS = {
    "hill_march": (HillMarchConfig, run_hill_march),
    "tez_chal": (TezChalConfig, run_tez_chal),
}


def run(label: str, crop: bool, difficulty: float) -> None:
    out_dir = OUTPUT_ROOT / label
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for video, drill, view in VIDEOS:
        config_cls, runner = DRILLS[drill]
        kwargs = dict(
            input_path=video, output_dir=out_dir, difficulty=difficulty, view=view,
            save_annotated_frames=True,
            report_metadata=ReportMetadata(cadet_name=f"{drill} {view} ({label})",
                                           drill_type=drill, session_id=video.stem),
        )
        if "crop_to_cadet" in {f.name for f in fields(config_cls)}:
            kwargs["crop_to_cadet"] = crop
        elif crop:
            raise SystemExit(f"{drill} has no crop_to_cadet option yet")

        print(f"[{label}] {video.name} — {drill} [{view}] ...", flush=True)
        started = time.monotonic()
        summary = runner(config_cls(**kwargs))[0]
        elapsed = round(time.monotonic() - started, 1)
        print(f"    steps={summary['iteration_count']} avg={summary['average_score']} "
              f"valid={summary['valid_scored_frames']}/{summary['processed_frames']} ({elapsed}s)")
        records.append({"video": video.name, "drill": drill, "view": view, "crop": crop,
                        "seconds": elapsed, **summary})
    (out_dir / "_summary.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


def _load_steps(results_json: Path) -> list[dict]:
    return json.loads(results_json.read_text(encoding="utf-8"))["peak_frames"]


def compare(a: str, b: str) -> None:
    sa = json.loads((OUTPUT_ROOT / a / "_summary.json").read_text())
    sb = json.loads((OUTPUT_ROOT / b / "_summary.json").read_text())
    rows = []
    for ra, rb in zip(sa, sb):
        steps_a, steps_b = _load_steps(Path(ra["results_json"])), _load_steps(Path(rb["results_json"]))
        params = [k for k in steps_a[0]["score"] if k != "total"] if steps_a else []

        def mean(steps, key):
            vals = [s["score"][key] for s in steps if s["score"].get(key) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        rows.append({
            "video": ra["video"], "drill": ra["drill"], "view": ra["view"],
            "valid_frames": [f"{ra['valid_scored_frames']}/{ra['processed_frames']}",
                             f"{rb['valid_scored_frames']}/{rb['processed_frames']}"],
            "steps": [ra["iteration_count"], rb["iteration_count"]],
            "average_score": [ra["average_score"], rb["average_score"]],
            "per_parameter_mean": {p: [mean(steps_a, p), mean(steps_b, p)] for p in params},
            "seconds": [ra["seconds"], rb["seconds"]],
        })
    out = OUTPUT_ROOT / f"_comparison_{a}_vs_{b}.json"
    out.write_text(json.dumps({"columns": [a, b], "videos": rows}, indent=2), encoding="utf-8")
    print(json.dumps({"columns": [a, b], "videos": rows}, indent=2))
    print(f"\nWritten to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label")
    parser.add_argument("--crop", dest="crop", action="store_true")
    parser.add_argument("--no-crop", dest="crop", action="store_false")
    parser.add_argument("--difficulty", type=float, default=2.0)
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"))
    args = parser.parse_args()
    if args.compare:
        compare(*args.compare)
    elif args.label:
        run(args.label, args.crop, args.difficulty)
    else:
        parser.error("pass --label (to run) or --compare A B")


if __name__ == "__main__":
    main()
