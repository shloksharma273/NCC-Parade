from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

MEDIA_DIR = BACKEND_ROOT / "media"
RAW_MEDIA_DIR = MEDIA_DIR / "raw"
ANNOTATED_MEDIA_DIR = MEDIA_DIR / "annotated"
FRAMES_MEDIA_DIR = MEDIA_DIR / "frames"
REPORTS_MEDIA_DIR = MEDIA_DIR / "reports"
REPORTS_DIR = BACKEND_ROOT / "reports"
DATABASE_DIR = BACKEND_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "drill_server.db"

SUPPORTED_DRILL_TYPES = {"kadam_tal", "salute"}


class Settings(BaseModel):
    app_name: str = "Drill Recognition Backend"
    version: str = "0.1.0"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    camera_id: int = int(os.getenv("CAMERA_ID", "0"))
    camera_width: int = int(os.getenv("CAMERA_WIDTH", "1280"))
    camera_height: int = int(os.getenv("CAMERA_HEIGHT", "720"))
    camera_fps: int = int(os.getenv("CAMERA_FPS", "30"))
    ml_difficulty: float = float(os.getenv("DIFFICULTY", "2.0"))
    ml_output_dir: Path = BACKEND_ROOT / "ml_output"


settings = Settings()


def ensure_directories() -> None:
    for path in (
        RAW_MEDIA_DIR,
        ANNOTATED_MEDIA_DIR,
        FRAMES_MEDIA_DIR,
        REPORTS_MEDIA_DIR,
        REPORTS_DIR,
        DATABASE_DIR,
        settings.ml_output_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
