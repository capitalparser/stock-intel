"""Build US/KR dual-regime reads from percentile-backed market indicators."""

from __future__ import annotations

from dashboard.percentile import (
    DimensionSpec,
    RISK_HIGH,
    RISK_LOW,
    dimension_state,
    percentile_rank,
    severity_rank,
)

US_SPECS = {
    "breadth": DimensionSpec("breadth", "시장 폭", RISK_LOW),
    "sentiment": DimensionSpec("sentiment", "시장 심리", RISK_HIGH, warn_guardrail=20.0),
    "rates": DimensionSpec("rates", "금리", RISK_HIGH, warn_guardrail=5.0),
    "fx": DimensionSpec("fx", "달러", RISK_HIGH),
    "commodities": DimensionSpec("commodities", "원자재", RISK_HIGH),
    "oil": DimensionSpec("oil", "유가", RISK_HIGH, stress_guardrail=100.0),
}
US_SYMBOL_DIM = {
    "RSP": "breadth", "S5FI": "breadth", "QQQ": "breadth", "IWM": "breadth",
    "^VIX": "sentiment", "^TNX": "rates", "DX-Y.NYB": "fx",
    "GLD": "commodities", "CPER": "commodities", "BZ=F": "oil", "CL=F": "oil",
}
KR_SPECS = {
    "breadth": DimensionSpec("breadth", "코스닥/코스피 상대강도", RISK_LOW),
    "sentiment": DimensionSpec("sentiment", "한국 변동성", RISK_HIGH),
    "fx": DimensionSpec("fx", "원화", RISK_HIGH, warn_guardrail=1450.0),
    "flow": DimensionSpec("flow", "외국인 수급", RISK_LOW),
}
KR_SYMBOL_DIM = {
    "KOSPI_BREADTH": "breadth", "VKOSPI": "sentiment", "KOSPI_RV": "sentiment",
    "USDKRW=X": "fx", "FOREIGN_NET": "flow",
}
_MARKET = {
    "US": (US_SPECS, US_SYMBOL_DIM, "SPY"),
    "KR": (KR_SPECS, KR_SYMBOL_DIM, "KOSPI"),
}


def _f(v):
    return None if v is None else float(v)


def build_market_regime(indicators: list[dict], *, market: str) -> dict:
    specs, symbol_dim, index_symbol = _MARKET[market]
    by_dim: dict[str, list[dict]] = {d: [] for d in specs}
    index_day = 0.0
    for item in indicators:
        sym = str(item.get("symbol"))
        if sym == index_symbol:
            index_day = _f(item.get("day_change_pct")) or 0.0
        dim = symbol_dim.get(sym)
        if dim in by_dim:
            by_dim[dim].append(item)

    axis_reads: list[dict] = []
    gaps: list[str] = []
    states: dict[str, str] = {}
    for dim, spec in specs.items():
        items = by_dim[dim]
        if not items:
            gaps.append(f"{spec.label}({dim}) 실데이터 미연결")
            axis_reads.append({"dimension": dim, "label": spec.label, "state": "unavailable",
                               "pctile": None, "read": f"{spec.label} 실데이터 미연결", "symbols": []})
            states[dim] = "unavailable"
            continue
        # 대표 percentile은 state를 결정한 바로 그 심볼의 percentile로 잡는다
        # (worst-state 심볼). 그래야 axis_reads의 pctile↔state가 근거-결론으로
        # 일치한다 (code review 2026-06-04 should-fix). 동률이면 먼저 본 심볼 유지.
        worst = "supportive"
        rep_pct = None
        rep_rank = -2  # "unavailable"(-1)보다 낮게 둬서 첫 유효 심볼이 항상 대표를 설정
        rep_item = None
        for it in items:
            val = _f(it.get("value"))
            if val is None:
                continue
            st = dimension_state(spec, val, it.get("series") or [])
            if severity_rank(st) > rep_rank:
                rep_rank = severity_rank(st)
                worst = st
                rep_pct = percentile_rank(it.get("series") or [], val)
                rep_item = it
        states[dim] = worst
        read = _axis_read(spec.label, worst)
        # proxy 라벨은 축의 *어느* 심볼이든 proxy면 보존한다(worst-state 심볼이 proxy가
        # 아니어도 사라지지 않게) — code review 2026-06-04 should-fix. v1.1에서 flow 축에
        # 실제 외국인 순매수(non-proxy)가 EWY(proxy)와 함께 들어올 때를 대비.
        source_kind = None
        if rep_item is not None and rep_item.get("source_kind"):
            source_kind = str(rep_item.get("source_kind"))
            read = str(rep_item.get("read") or read)
        else:
            proxy_item = next((it for it in items if it.get("source_kind") == "proxy"), None)
            if proxy_item is not None:
                source_kind = "proxy"
                read = str(proxy_item.get("read") or read)
        axis_read = {"dimension": dim, "label": spec.label, "state": worst,
                     "pctile": rep_pct, "read": read,
                     "symbols": [str(it.get("symbol")) for it in items]}
        if source_kind:
            axis_read["source_kind"] = source_kind
        axis_reads.append(axis_read)

    regime = _compose_regime(market, index_day, states)
    return {"market": market, "regime": regime, "why_it_matters": _why(market, regime),
            "next_action": _next_action(regime), "axis_reads": axis_reads, "data_gaps": gaps}


def _warning_dims(states: dict[str, str]) -> set[str]:
    return {d for d, s in states.items() if s in {"warning", "stressed"}}


def _compose_regime(market: str, index_day: float, states: dict[str, str]) -> str:
    if all(s == "unavailable" for s in states.values()):
        return "conditional"  # 데이터 부재를 risk-on으로 단정하지 않는다 (codex review)
    warn = _warning_dims(states)
    index_strong = index_day > 0
    fragile_axes = {"breadth", "rates", "oil"} if market == "US" else {"breadth", "flow", "fx"}
    riskoff_pair = {"sentiment", "oil"} if market == "US" else {"sentiment", "fx"}
    # risk-off는 fragile rally보다 우선한다 (의도적): 방어 페어가 동시 경고면 지수 강세보다 위험 우선.
    if riskoff_pair <= warn:
        return "risk-off"
    if index_strong and (fragile_axes & warn):
        return "fragile rally"
    if warn:
        return "conditional"
    return "risk-on"


def _axis_read(label: str, state: str) -> str:
    return {
        "stressed": f"{label} 압력이 높아 위험 관리 우선",
        "warning": f"{label} 경고 신호. 상승의 질 확인 필요",
        "unavailable": f"{label} 실데이터 미연결",
        "supportive": f"{label} 우호적 또는 중립",
    }[state]


def _why(market: str, regime: str) -> str:
    name = "미국" if market == "US" else "한국"
    return {
        "fragile rally": f"{name} 지수는 강하지만 내부 체력·비용 지표가 랠리의 질을 의심하는 구간",
        "risk-off": f"{name} 변동성·환율/유가가 동시에 올라 방어가 우선인 구간",
        "conditional": f"{name} 일부 매크로 지표가 경고를 내 종목별 선별이 필요한 구간",
        "risk-on": f"{name} 주요 매크로 지표가 위험자산에 우호적인 구간",
    }[regime]


def _next_action(regime: str) -> str:
    return {
        "fragile rally": "신규 진입 강도를 낮추고 후보를 압축",
        "risk-off": "방어 전환 감시",
        "conditional": "후보 압축",
        "risk-on": "가격 매력 있는 후보부터 검토",
    }[regime]


from dashboard.regime_history import detect_transition  # noqa: E402


def build_dual_regime(us_indicators, kr_indicators, *, history=None, as_of=None) -> dict:
    history = history or []
    us = build_market_regime(us_indicators, market="US")
    kr = build_market_regime(kr_indicators, market="KR")
    return {"as_of": as_of, "us": us, "kr": kr,
            "transitions": {"us": detect_transition(history, us, "us"),
                            "kr": detect_transition(history, kr, "kr")}}
