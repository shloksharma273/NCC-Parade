from __future__ import annotations

import math
import os

from dotenv import load_dotenv

load_dotenv()

MIN_DIFFICULTY = 0.0
MAX_DIFFICULTY = 5.0
DEFAULT_DIFFICULTY = 2.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def load_difficulty(cli_value: float | None = None) -> float:
    if cli_value is not None:
        return _clamp(cli_value, MIN_DIFFICULTY, MAX_DIFFICULTY)

    env_value = os.getenv("DIFFICULTY")
    if env_value is not None:
        try:
            return _clamp(float(env_value), MIN_DIFFICULTY, MAX_DIFFICULTY)
        except ValueError:
            pass

    return DEFAULT_DIFFICULTY


def scaled_tolerances(
    difficulty: float,
    perfect_at_easy: float,
    perfect_at_hard: float,
    fail_at_easy: float,
    fail_at_hard: float,
) -> tuple[float, float]:
    t = _clamp(difficulty / MAX_DIFFICULTY, 0.0, 1.0)
    perfect = _lerp(perfect_at_easy, perfect_at_hard, t)
    fail = _lerp(fail_at_easy, fail_at_hard, t)
    return perfect, fail
