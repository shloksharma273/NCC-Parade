from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .geometry import score_by_max, score_by_tolerance

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def _clamp_difficulty(value: float) -> float:
    return max(0.0, min(5.0, value))


def load_difficulty(override: float | None = None) -> float:
    if override is not None:
        return _clamp_difficulty(float(override))

    load_dotenv(ENV_PATH)
    raw = os.getenv("DIFFICULTY", "2")
    return _clamp_difficulty(float(raw))


@dataclass(frozen=True)
class DifficultyProfile:
    level: float

    @classmethod
    def load(cls, override: float | None = None) -> DifficultyProfile:
        return cls(level=load_difficulty(override))

    def _leniency_multiplier(self) -> float:
        # 0 -> 2.0x wider thresholds, 5 -> 1.0x base thresholds
        return 2.0 - (self.level / 5.0)

    def _strictness_multiplier(self) -> float:
        # 0 -> 1.0x, 5 -> 0.6x tighter thresholds
        return 1.0 - (self.level / 5.0) * 0.4

    def adjust_max_thresholds(self, perfect_max: float, fail_max: float) -> tuple[float, float]:
        multiplier = self._leniency_multiplier() * self._strictness_multiplier()
        return perfect_max * multiplier, fail_max * multiplier

    def adjust_tolerance_thresholds(
        self, perfect_tolerance: float, fail_tolerance: float
    ) -> tuple[float, float]:
        multiplier = self._leniency_multiplier() * self._strictness_multiplier()
        return perfect_tolerance * multiplier, fail_tolerance * multiplier

    def score_max(self, value: float, perfect_max: float, fail_max: float) -> float:
        adjusted_perfect, adjusted_fail = self.adjust_max_thresholds(perfect_max, fail_max)
        return score_by_max(value, adjusted_perfect, adjusted_fail)

    def score_tolerance(
        self, value: float, target: float, perfect_tolerance: float, fail_tolerance: float
    ) -> float:
        adjusted_perfect, adjusted_fail = self.adjust_tolerance_thresholds(
            perfect_tolerance, fail_tolerance
        )
        return score_by_tolerance(value, target, adjusted_perfect, adjusted_fail)
