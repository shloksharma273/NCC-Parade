from __future__ import annotations

from datetime import datetime

from ..db.repositories import SessionRepository


def generate_session_id(repo: SessionRepository) -> str:
    date_prefix = datetime.now().strftime("%Y%m%d")
    prefix = f"DRILL-{date_prefix}-"
    count = repo.count_sessions_for_date(date_prefix) + 1
    return f"{prefix}{count:04d}"
