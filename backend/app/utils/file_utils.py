from __future__ import annotations

import shutil
from pathlib import Path


def copy_file(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def media_url(relative_path: str) -> str:
    return f"/media/{relative_path.lstrip('/')}"
