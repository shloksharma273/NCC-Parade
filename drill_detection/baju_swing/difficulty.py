from __future__ import annotations

import math  # noqa: F401  (kept for parity with kadam_tal reference)
import os

from dotenv import load_dotenv

# --- Copied verbatim from drill_detection/kadam_tal/difficulty.py -----------
# The package is self-contained (PRD module layout) and does NOT import the
# difficulty helpers from kadam_tal at runtime.

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


def scaled_value(difficulty: float, at_easy: float, at_hard: float) -> float:
    # Single-value linear interpolation from easy (difficulty 0) to hard (5).
    # Used for the front-view swing-spread full-reach target (§10.2): higher
    # difficulty demands a higher fist to earn full marks.
    t = _clamp(difficulty / MAX_DIFFICULTY, 0.0, 1.0)
    return _lerp(at_easy, at_hard, t)


def scaled_tolerances(
    difficulty: float,
    perfect_at_easy: float,
    perfect_at_hard: float,
    fail_at_easy: float,
    fail_at_hard: float,
) -> tuple[float, float]:
    # Linear interpolation from easy (difficulty 0) to hard (difficulty 5).
    #   t = difficulty / 5  ->  perfect = lerp(easy, hard, t);  fail = lerp(easy, hard, t)
    # Lower difficulty => wider (more lenient) tolerances; higher => tighter.
    t = _clamp(difficulty / MAX_DIFFICULTY, 0.0, 1.0)
    perfect = _lerp(perfect_at_easy, perfect_at_hard, t)
    fail = _lerp(fail_at_easy, fail_at_hard, t)
    return perfect, fail
