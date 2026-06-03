"""Derive macro state cockpit reads from market indicators and issue cards."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

DIMENSIONS = ("breadth", "sentiment", "rates", "fx", "commodities", "oil")

SYMBOL_DIMENSION = {
    "RSP": "breadth",
    "S5FI": "breadth",
    "QQQ": "breadth",
    "IWM": "breadth",
    "^VIX": "sentiment",
    "^TNX": "rates",
    "^IRX": "rates",
    "DX-Y.NYB": "fx",
    "USDKRW=X": "fx",
    "GLD": "commodities",
    "CPER": "commodities",
    "BZ=F": "oil",
    "CL=F": "oil",
}


def build_macro_state(payload: dict[str, Any]) -> dict[str, Any]:
    indicators = list(payload.get("market_indicators") or [])
    issue_cards = [_issue_card(item) for item in payload.get("issues") or []]
    reads, gaps = _indicator_reads(indicators)
    warning_dims = {
        item["dimension"] for item in reads if item["state"] in {"warning", "stressed"}
    }
    spy_strong = _positive_symbol(indicators, "SPY")

    if spy_strong and {"breadth", "rates", "oil"} & warning_dims:
        current_state = "fragile rally"
        why = "지수는 강하지만 breadth·금리·유가 중 일부가 랠리의 질을 의심하는 구간"
        next_action = "신규 진입 강도를 낮추고 후보를 압축"
    elif "sentiment" in warning_dims and "oil" in warning_dims:
        current_state = "risk-off"
        why = "변동성과 유가가 동시에 올라 위험자산 방어가 우선인 구간"
        next_action = "방어 전환 감시"
    elif warning_dims:
        current_state = "conditional"
        why = "일부 매크로 지표가 경고를 내고 있어 종목별 선별이 필요한 구간"
        next_action = "후보 압축"
    else:
        current_state = "risk-on"
        why = "주요 매크로 지표가 위험자산에 우호적인 구간"
        next_action = "가격 매력 있는 후보부터 검토"

    return {
        "current_state": current_state,
        "why_it_matters": why,
        "next_action": next_action,
        "indicator_reads": reads,
        "issues": issue_cards,
        "watchlist_impact": _watchlist_impact(current_state, warning_dims),
        "data_gaps": gaps,
    }


def _indicator_reads(indicators: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    by_dimension: dict[str, list[dict[str, Any]]] = {
        dimension: [] for dimension in DIMENSIONS
    }
    for item in indicators:
        dimension = SYMBOL_DIMENSION.get(
            str(item.get("symbol")),
            _dimension_from_group(str(item.get("group", ""))),
        )
        if dimension in by_dimension:
            by_dimension[dimension].append(item)

    reads: list[dict[str, Any]] = []
    gaps: list[str] = []
    for dimension in DIMENSIONS:
        items = by_dimension[dimension]
        if not items:
            gap = f"{dimension} 실데이터 미연결"
            gaps.append(gap)
            reads.append(
                {
                    "dimension": dimension,
                    "label": _dimension_label(dimension),
                    "state": "unavailable",
                    "read": gap,
                    "symbols": [],
                }
            )
            continue
        state = _dimension_state(dimension, items)
        reads.append(
            {
                "dimension": dimension,
                "label": _dimension_label(dimension),
                "state": state,
                "read": _dimension_read(dimension, state),
                "symbols": [str(item.get("symbol")) for item in items],
            }
        )
    return reads, gaps


def _dimension_from_group(group: str) -> str:
    if "breadth" in group or "동일가중" in group:
        return "breadth"
    if "심리" in group or "변동성" in group:
        return "sentiment"
    if "금리" in group:
        return "rates"
    if "환율" in group or "달러" in group:
        return "fx"
    if "원자재" in group:
        return "commodities"
    if "유가" in group:
        return "oil"
    return ""


def _dimension_state(dimension: str, items: list[dict[str, Any]]) -> str:
    prices = {str(item.get("symbol")): _float(item.get("price")) for item in items}
    changes = {
        str(item.get("symbol")): _float(item.get("day_change_pct")) or 0.0 for item in items
    }
    if dimension == "breadth":
        s5fi = prices.get("S5FI")
        if s5fi is not None and s5fi < 60:
            return "warning"
        if changes.get("RSP", 0.0) < 0 and changes.get("QQQ", 0.0) >= 0:
            return "warning"
    if dimension == "sentiment":
        vix = prices.get("^VIX")
        if vix is not None and vix >= 22:
            return "stressed"
        if vix is not None and (vix >= 16 or changes.get("^VIX", 0.0) > 3):
            return "warning"
    if dimension == "rates":
        tnx = prices.get("^TNX")
        if tnx is not None and tnx >= 4.5:
            return "warning"
    if dimension == "fx":
        if changes.get("DX-Y.NYB", 0.0) > 0.3 or changes.get("USDKRW=X", 0.0) > 0.5:
            return "warning"
    if dimension == "commodities":
        if changes.get("GLD", 0.0) > 1.0 or changes.get("CPER", 0.0) > 1.0:
            return "warning"
    if dimension == "oil":
        brent = prices.get("BZ=F")
        wti = prices.get("CL=F")
        if (brent is not None and brent >= 95) or (wti is not None and wti >= 90):
            return "stressed"
    return "supportive"


def _dimension_read(dimension: str, state: str) -> str:
    label = _dimension_label(dimension)
    if state == "stressed":
        return f"{label} 압력이 높아 위험 관리 우선"
    if state == "warning":
        return f"{label} 경고 신호. 지수 상승의 질 확인 필요"
    return f"{label} 우호적 또는 중립"


def _watchlist_impact(current_state: str, warning_dims: set[str]) -> dict[str, str]:
    return {
        "growth_ai": "chase 제한" if current_state == "fragile rally" else "가격 매력 확인",
        "cyclicals": "금리·유가 확인 후 압축" if {"rates", "oil"} & warning_dims else "선별 유지",
        "energy_defense": "상대강도 관찰" if "oil" in warning_dims else "중립",
        "korea": "USDKRW·유가 부담 점검" if {"fx", "oil"} & warning_dims else "중립",
    }


def _issue_card(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "theme": str(item.get("theme", "기타")),
        "title": str(item.get("title", "")),
        "state": str(item.get("state", "active")),
        "summary": str(item.get("summary", "")),
        "triggers": [str(value) for value in item.get("triggers", [])],
        "source_gaps": [str(value) for value in item.get("source_gaps", [])],
    }


def _positive_symbol(indicators: Iterable[dict[str, Any]], symbol: str) -> bool:
    for item in indicators:
        if item.get("symbol") == symbol:
            return (_float(item.get("day_change_pct")) or 0.0) > 0
    return False


def _float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _dimension_label(dimension: str) -> str:
    return {
        "breadth": "시장 폭",
        "sentiment": "시장 심리",
        "rates": "금리",
        "fx": "환율",
        "commodities": "원자재",
        "oil": "유가",
    }[dimension]
