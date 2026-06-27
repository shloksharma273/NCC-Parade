from __future__ import annotations

import shutil

from ..config import BACKEND_ROOT, ensure_directories
from ..db.repositories import SessionRepository


class StorageService:
    def __init__(self) -> None:
        ensure_directories()

    def storage_available(self) -> bool:
        try:
            test_file = BACKEND_ROOT / "database" / ".storage_test"
            test_file.write_text("ok")
            test_file.unlink()
            return shutil.disk_usage(BACKEND_ROOT).free > 100 * 1024 * 1024
        except OSError:
            return False


storage_service = StorageService()
