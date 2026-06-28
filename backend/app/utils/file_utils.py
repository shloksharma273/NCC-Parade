from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


def copy_file(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def media_url(relative_path: str) -> str:
    return f"/media/{relative_path.lstrip('/')}"


def sanitize_cadet_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "Cadet"


def parse_recorded_datetime(recorded_at: str | None) -> datetime:
    if not recorded_at:
        return datetime.now(timezone.utc)
    normalized = recorded_at.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(timezone.utc)


def build_report_pdf_filename(cadet_name: str, recorded_at: str | None) -> str:
    name = sanitize_cadet_name(cadet_name)
    date_part = parse_recorded_datetime(recorded_at).strftime("%m-%d")
    return f"{name}_{date_part}.pdf"


def unique_report_pdf_path(directory: Path, cadet_name: str, recorded_at: str | None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    base = build_report_pdf_filename(cadet_name, recorded_at)[:-4]
    candidate = directory / f"{base}.pdf"
    if not candidate.exists():
        return candidate

    suffix = 2
    while (directory / f"{base}_{suffix}.pdf").exists():
        suffix += 1
    return directory / f"{base}_{suffix}.pdf"
