from __future__ import annotations

from typing import Any

from .database import get_connection


class SessionRepository:
    def create_session(self, data: dict[str, Any]) -> dict[str, Any]:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, cadet_id, cadet_name, squad, unit, drill_type, attempt_number,
                    camera_id, camera_view, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["session_id"],
                    data.get("cadet_id"),
                    data["cadet_name"],
                    data.get("squad"),
                    data.get("unit"),
                    data["drill_type"],
                    data["attempt_number"],
                    data["camera_id"],
                    data.get("camera_view"),
                    data["status"],
                    data["created_at"],
                ),
            )
        return self.get_session(data["session_id"])

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_session(self, session_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_session(session_id)

        columns = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [session_id]
        with get_connection() as conn:
            conn.execute(f"UPDATE sessions SET {columns} WHERE session_id = ?", values)
        return self.get_session(session_id)

    def list_sessions(
        self,
        limit: int = 20,
        drill_type: str | None = None,
        cadet_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM sessions WHERE 1=1"
        params: list[Any] = []
        if drill_type:
            query += " AND drill_type = ?"
            params.append(drill_type)
        if cadet_id:
            query += " AND cadet_id = ?"
            params.append(cadet_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def count_sessions_for_date(self, date_prefix: str) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM sessions WHERE session_id LIKE ?",
                (f"DRILL-{date_prefix}-%",),
            ).fetchone()
        return int(row["count"])

    def next_attempt_number(self, cadet_id: str | None, drill_type: str) -> int:
        if not cadet_id:
            return 1
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT MAX(attempt_number) AS max_attempt
                FROM sessions
                WHERE cadet_id = ? AND drill_type = ?
                """,
                (cadet_id, drill_type),
            ).fetchone()
        current = row["max_attempt"] if row and row["max_attempt"] is not None else 0
        return int(current) + 1


class ProgressRepository:
    def add_event(
        self,
        session_id: str,
        status: str,
        stage: str,
        progress: int,
        message: str,
        created_at: str,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO progress_events (session_id, status, stage, progress, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, status, stage, progress, message, created_at),
            )

    def get_latest(self, session_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM progress_events
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None
