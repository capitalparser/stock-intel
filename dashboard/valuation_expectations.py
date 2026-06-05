"""Valuation-expectations verdict engine (Plan 6).

v1: 성장·FCF only (가이던스/리비전 미반영). This module is pure and
deterministic; source gaps are surfaced in ``data_gaps`` instead of hidden.
"""

from __future__ import annotations

from typing import Any

_HIGH_ABS_PE = 40.0
_SCOPE_WARNING = "v1: 성장·FCF only (가이던스/리비전 미반영)"


def _growth_adjusted_multiple(forward_pe, eps_growth_pct, rev_growth_pct) -> float | None:
    if forward_pe is None:
        return None
    forward = float(forward_pe)
    if forward <= 0:
        return None
    eps = float(eps_growth_pct) if eps_growth_pct is not None else 0.0
    rev = float(rev_growth_pct) if rev_growth_pct is not None else 0.0
    denom = max(eps, rev * 0.5)
    if denom <= 0:
        return None
    return forward / denom


def _fcf_band(fcf_margin_pct) -> str:
    if fcf_margin_pct is None:
        return "unknown"
    margin = float(fcf_margin_pct)
    if margin >= 30:
        return "strong"
    if margin >= 15:
        return "acceptable"
    return "weak"


def expectation_verdict(
    payload: dict[str, Any] | None = None,
    *,
    forward_pe=None,
    rev_growth_pct=None,
    eps_growth_pct=None,
    fcf_margin_pct=None,
    revision_dir=None,
) -> dict:
    if payload is not None:
        forward_pe = payload.get("forward_pe", payload.get("pe_forward", forward_pe))
        growth = payload.get("growth_rate")
        if growth is not None and rev_growth_pct is None and eps_growth_pct is None:
            rev_growth_pct = _ratio_to_pct(growth)
            eps_growth_pct = _ratio_to_pct(growth)
        rev_growth_pct = payload.get("rev_growth_pct", rev_growth_pct)
        eps_growth_pct = payload.get("eps_growth_pct", eps_growth_pct)
        fcf_margin_pct = payload.get("fcf_margin_pct", fcf_margin_pct)
        if fcf_margin_pct is None and payload.get("fcf_yield") is not None:
            fcf_margin_pct = _ratio_to_pct(payload["fcf_yield"])
        revision_dir = payload.get("revision_dir", revision_dir)

    data_gaps = ["가이던스 데이터 부족(yfinance 미제공)"]
    if revision_dir is None:
        data_gaps.append("리비전 방향 데이터 부족")

    forward = _positive_float(forward_pe)
    rev = _optional_float(rev_growth_pct)
    eps = _optional_float(eps_growth_pct)
    gam = _growth_adjusted_multiple(forward, eps, rev)
    fcf = _fcf_band(fcf_margin_pct)

    if forward is None or (eps is None and rev is None):
        return _result("데이터 부족", "성장률 또는 PE 없음", gam, fcf, data_gaps)

    growth_neg = (eps is not None and eps < 0) or (rev is not None and rev < 0)
    if (revision_dir == "down" or growth_neg) and forward >= _HIGH_ABS_PE:
        return _result("위험", "이익 추정 하향/역성장 중 고배수", gam, fcf, data_gaps)

    if gam is None:
        return _result("데이터 부족", "성장률 또는 PE 없음", gam, fcf, data_gaps)

    if gam > 2.2:
        return _result("과열", "성장 대비 배수가 과도", gam, fcf, data_gaps)
    if gam > 1.4:
        return _result("기대치 부담", "주가가 더 큰 성장 서프라이즈를 요구하는 구간", gam, fcf, data_gaps)
    if gam < 0.8 and not growth_neg:
        return _result("저평가 후보", "성장 대비 배수가 낮아 재평가 여지", gam, fcf, data_gaps)
    if fcf == "weak":
        return _result("기대치 부담", "밸류 균형이나 현금창출 약함", gam, fcf, data_gaps)
    return _result("정당화 가능", "성장·현금이 현재 배수를 대체로 정당화", gam, fcf, data_gaps)


def _result(verdict: str, reason: str, gam: float | None, fcf: str, data_gaps: list[str]) -> dict:
    return {
        "verdict": verdict,
        "reason": reason,
        "read": f"{_SCOPE_WARNING} · {reason}",
        "growth_adjusted_multiple": round(gam, 2) if gam is not None else None,
        "fcf_band": fcf,
        "data_gaps": list(data_gaps),
    }


def _optional_float(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _positive_float(value) -> float | None:
    out = _optional_float(value)
    if out is None or out <= 0:
        return None
    return out


def _ratio_to_pct(value) -> float:
    return float(value) * 100
