"""Percentile-based macro dimension state with absolute guardrails (ADR-0001)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

MIN_SERIES = 30
RISK_HIGH = "risk_up_when_high"
RISK_LOW = "risk_up_when_low"

_SEVERITY = {"unavailable": -1, "supportive": 0, "warning": 1, "stressed": 2}


def percentile_rank(series: Sequence[float | None], value: float) -> float | None:
    """Fraction of `series` <= `value` in [0,1]. None if usable series < MIN_SERIES."""
    clean = [float(v) for v in series if v is not None]
    if len(clean) < MIN_SERIES:
        return None
    below = sum(1 for v in clean if v <= value)
    return round(below / len(clean), 4)


def severity_rank(state: str) -> int:
    return _SEVERITY[state]


def worse_state(a: str, b: str) -> str:
    return a if _SEVERITY[a] >= _SEVERITY[b] else b
