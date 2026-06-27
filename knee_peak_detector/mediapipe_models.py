from __future__ import annotations

import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

MODEL_URLS = {
    "holistic_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/holistic_landmarker/"
        "holistic_landmarker/float16/latest/holistic_landmarker.task"
    ),
}


def ensure_models(models_dir: Path = MODELS_DIR) -> Path:
    models_dir.mkdir(parents=True, exist_ok=True)
    holistic_path = models_dir / "holistic_landmarker.task"

    for filename, url in MODEL_URLS.items():
        dest = models_dir / filename
        if dest.exists() and dest.stat().st_size > 0:
            continue
        print(f"Downloading {filename}...")
        urllib.request.urlretrieve(url, dest)
        print(f"Saved to {dest}")

    return holistic_path
