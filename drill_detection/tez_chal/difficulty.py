from __future__ import annotations

# --- Copied verbatim from slow_march / kadam_tal difficulty.py so the package
# --- is self-contained and does NOT import another drill at runtime.
MIN_DIFFICULTY = 0.0
MAX_DIFFICULTY = 5.0
DEFAULT_DIFFICULTY = 2.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def scaled_tolerances(
    difficulty: float,
    perfect_at_easy: float,
    perfect_at_hard: float,
    fail_at_easy: float,
    fail_at_hard: float,
) -> tuple[float, float]:
    # Linear interpolation on t = difficulty / MAX_DIFFICULTY in [0, 1]:
    #   easy (difficulty 0)  -> wider tolerances (lenient)
    #   hard (difficulty 5)  -> tighter tolerances (strict)
    t = _clamp(difficulty / MAX_DIFFICULTY, 0.0, 1.0)
    perfect = _lerp(perfect_at_easy, perfect_at_hard, t)
    fail = _lerp(fail_at_easy, fail_at_hard, t)
    return perfect, fail
