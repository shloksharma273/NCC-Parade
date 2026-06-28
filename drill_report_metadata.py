from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class ReportMetadata:
    cadet_name: str = "Unknown Cadet"
    cadet_id: str | None = None
    session_id: str = ""
    attempt_number: int = 1
    drill_type: str = "kadam_tal"
    recorded_at: str | None = None

    @classmethod
    def from_session(cls, session: dict) -> ReportMetadata:
        return cls(
            cadet_name=session.get("cadet_name") or "Unknown Cadet",
            cadet_id=session.get("cadet_id"),
            session_id=session.get("session_id") or "",
            attempt_number=int(session.get("attempt_number") or 1),
            drill_type=session.get("drill_type") or "kadam_tal",
            recorded_at=session.get("stopped_at") or session.get("started_at") or session.get("created_at"),
        )

    def to_dict(self) -> dict:
        return asdict(self)


DRILL_TYPE_LABELS = {
    "kadam_tal": "Kadam Tal",
    "salute": "Salute",
}


def drill_type_label(drill_type: str) -> str:
    return DRILL_TYPE_LABELS.get(drill_type, drill_type.replace("_", " ").title())
