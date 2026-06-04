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


WARN_HIGH_PCT = 0.85
STRESS_HIGH_PCT = 0.95
WARN_LOW_PCT = 0.15
STRESS_LOW_PCT = 0.05


@dataclass(frozen=True)
class DimensionSpec:
    dimension: str
    label: str
    direction: str
    warn_guardrail: float | None = None
    stress_guardrail: float | None = None


def _percentile_state(spec: DimensionSpec, value: float, series) -> str:
    pct = percentile_rank(series, value)
    if pct is None:
        return "unavailable"
    if spec.direction == RISK_HIGH:
        if pct >= STRESS_HIGH_PCT:
            return "stressed"
        if pct >= WARN_HIGH_PCT:
            return "warning"
        return "supportive"
    if pct <= STRESS_LOW_PCT:
        return "stressed"
    if pct <= WARN_LOW_PCT:
        return "warning"
    return "supportive"


def _guardrail_state(spec: DimensionSpec, value: float) -> str:
    def hit(threshold: float | None) -> bool:
        if threshold is None:
            return False
        return value >= threshold if spec.direction == RISK_HIGH else value <= threshold

    if hit(spec.stress_guardrail):
        return "stressed"
    if hit(spec.warn_guardrail):
        return "warning"
    return "supportive"


def dimension_state(spec: DimensionSpec, value: float, series) -> str:
    pct_state = _percentile_state(spec, value, series)
    guard_state = _guardrail_state(spec, value)
    if pct_state == "unavailable":
        # series 없음: 가드레일이 발동하면 그 state, 아니면 unavailable (supportive로 단정 안 함).
        return guard_state if guard_state != "supportive" else "unavailable"
    return worse_state(pct_state, guard_state)
