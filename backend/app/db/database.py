from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..config import DATABASE_PATH, ensure_directories


def init_db(db_path: Path = DATABASE_PATH) -> None:
    ensure_directories()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                cadet_id TEXT,
                cadet_name TEXT NOT NULL,
                drill_type TEXT NOT NULL,
                attempt_number INTEGER NOT NULL DEFAULT 1,
                camera_id TEXT NOT NULL,
                status TEXT NOT NULL,
                video_path TEXT,
                report_path TEXT,
                score INTEGER,
                result TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                stopped_at TEXT,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS progress_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                progress INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


@contextmanager
def get_connection(db_path: Path = DATABASE_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
