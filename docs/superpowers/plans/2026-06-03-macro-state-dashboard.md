# Macro State Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a macro state cockpit to the existing stock intelligence dashboard so it shows fixed macro indicators, the current dominant market issue, and watchlist impact before candidate review.

**Architecture:** Reuse the existing `dashboard/` package, snapshot cache, and renderer. Add a focused `dashboard/macro_state.py` derivation layer that converts indicator records and issue cards into Korean reader-facing state, then render that state inside the current HTML/Markdown dashboard without changing candidate scoring.

**Tech Stack:** Python 3.12, dataclasses, stdlib HTML escaping, yfinance-backed provider snapshots, pytest, existing PAS Workbench dashboard CSS.

---

## File Structure

- Create `dashboard/macro_state.py`: macro indicator groups, issue cards, derived cockpit state, and watchlist impact logic.
- Create `tests/test_macro_state.py`: deterministic tests for macro state derivation.
- Modify `dashboard/models.py`: add optional `MacroState`, `MacroIssue`, `MacroIndicatorRead`, and `WatchlistImpact` dataclasses plus parser support.
- Modify `dashboard/providers/macro.py`: expand quote symbols to breadth, sentiment, rates, FX, commodities, and oil.
- Modify `dashboard/snapshot.py`: include `macro_state` in the snapshot from provider output.
- Modify `dashboard/live.py`: overlay `macro_state` and curated issue cards into `DashboardInput`.
- Modify `dashboard/render.py`: render the macro state cockpit in HTML and Markdown.
- Modify `dashboard/sample_data.py` or `dashboard/market_insights.py`: include one curated geopolitics issue card for deterministic fallback.
- Modify `tests/test_dashboard_models.py`: verify macro state parsing.
- Modify `tests/test_snapshot.py`: verify snapshot carries macro state payload.
- Modify `tests/test_live.py`: verify live overlay preserves macro state and issue cards.
- Modify `tests/test_dashboard_render.py`: verify Korean labels and no raw implementation terms.

---

### Task 1: Macro State Derivation

**Files:**
- Create: `dashboard/macro_state.py`
- Test: `tests/test_macro_state.py`

- [ ] **Step 1: Write failing derivation tests**

Create `tests/test_macro_state.py`:

```python
from dashboard.macro_state import build_macro_state


def test_build_macro_state_derives_fragile_rally_from_equity_strength_and_macro_warnings():
    payload = {
        "market_indicators": [
            {"symbol": "SPY", "name": "S&P 500 ETF", "group": "미국 대형주", "price": 7600.0, "day_change_pct": 0.7, "read": "미국 대형주 강세"},
            {"symbol": "RSP", "name": "S&P 500 동일가중", "group": "breadth", "price": 180.0, "day_change_pct": -0.2, "read": "동일가중 약세"},
            {"symbol": "S5FI", "name": "S&P 500 50일선 상회 비율", "group": "breadth", "price": 57.0, "day_change_pct": -3.0, "read": "breadth 약화"},
            {"symbol": "^TNX", "name": "미국 10년물", "group": "금리", "price": 4.52, "day_change_pct": 1.8, "read": "금리 압박"},
            {"symbol": "BZ=F", "name": "Brent", "group": "유가", "price": 96.0, "day_change_pct": 1.2, "read": "유가 위험"},
            {"symbol": "^VIX", "name": "VIX", "group": "심리", "price": 16.2, "day_change_pct": 4.0, "read": "변동성 상승"},
        ],
        "issues": [
            {
                "theme": "지정학",
                "title": "이란·이스라엘·레바논 협상 신뢰도 약화",
                "state": "unresolved",
                "summary": "휴전 기대는 남아 있지만 현장 충돌과 유가가 종전 신뢰도를 의심한다.",
                "triggers": ["Brent 95달러 위 고착", "10Y 4.5% 재상승", "VIX 동반 상승"],
                "source_gaps": ["헤즈볼라 묵시적 수용 여부"],
            }
        ],
    }

    state = build_macro_state(payload)

    assert state["current_state"] == "fragile rally"
    assert "지수는 강하지만" in state["why_it_matters"]
    assert state["next_action"] == "신규 진입 강도를 낮추고 후보를 압축"
    assert state["indicator_reads"][0]["dimension"] == "breadth"
    assert state["indicator_reads"][0]["state"] == "warning"
    assert state["issues"][0]["theme"] == "지정학"
    assert state["watchlist_impact"]["growth_ai"] == "chase 제한"


def test_build_macro_state_marks_missing_breadth_as_gap():
    state = build_macro_state({
        "market_indicators": [
            {"symbol": "SPY", "name": "S&P 500 ETF", "group": "미국 대형주", "price": 7600.0, "day_change_pct": 0.3, "read": "강세"},
            {"symbol": "^VIX", "name": "VIX", "group": "심리", "price": 14.8, "day_change_pct": -1.0, "read": "변동성 진정"},
        ],
        "issues": [],
    })

    breadth = next(item for item in state["indicator_reads"] if item["dimension"] == "breadth")
    assert breadth["state"] == "unavailable"
    assert "breadth 실데이터 미연결" in breadth["read"]
    assert "breadth 실데이터 미연결" in state["data_gaps"]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run pytest tests/test_macro_state.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'dashboard.macro_state'`.

- [ ] **Step 3: Implement minimal derivation layer**

Create `dashboard/macro_state.py`:

```python
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
    warning_dims = {item["dimension"] for item in reads if item["state"] in {"warning", "stressed"}}
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
    by_dimension: dict[str, list[dict[str, Any]]] = {dimension: [] for dimension in DIMENSIONS}
    for item in indicators:
        dimension = SYMBOL_DIMENSION.get(str(item.get("symbol")), _dimension_from_group(str(item.get("group", ""))))
        if dimension in by_dimension:
            by_dimension[dimension].append(item)

    reads: list[dict[str, Any]] = []
    gaps: list[str] = []
    for dimension in DIMENSIONS:
        items = by_dimension[dimension]
        if not items:
            gap = f"{dimension} 실데이터 미연결"
            gaps.append(gap)
            reads.append({
                "dimension": dimension,
                "label": _dimension_label(dimension),
                "state": "unavailable",
                "read": gap,
                "symbols": [],
            })
            continue
        state = _dimension_state(dimension, items)
        reads.append({
            "dimension": dimension,
            "label": _dimension_label(dimension),
            "state": state,
            "read": _dimension_read(dimension, state, items),
            "symbols": [str(item.get("symbol")) for item in items],
        })
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
    changes = {str(item.get("symbol")): _float(item.get("day_change_pct")) or 0.0 for item in items}
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


def _dimension_read(dimension: str, state: str, items: list[dict[str, Any]]) -> str:
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
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_macro_state.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add dashboard/macro_state.py tests/test_macro_state.py
git commit -m "Add macro state derivation"
```

---

### Task 2: Models And Parser Support

**Files:**
- Modify: `dashboard/models.py`
- Test: `tests/test_dashboard_models.py`

- [ ] **Step 1: Write failing parser test**

Append to `tests/test_dashboard_models.py`:

```python
def test_parse_dashboard_input_accepts_macro_state_payload():
    payload = {
        "as_of": "2026-06-03",
        "regime": {
            "verdict": "conditional",
            "risk_appetite": "risk-on",
            "rates": "rising",
            "dollar": "stable",
            "volatility": "elevated",
            "notes": ["지수는 강하지만 유가와 금리가 경고"],
        },
        "price_time": "2026-06-03T00:00:00+00:00",
        "market_indicators": [],
        "macro_state": {
            "current_state": "fragile rally",
            "why_it_matters": "지수는 강하지만 breadth·금리·유가 중 일부가 랠리의 질을 의심하는 구간",
            "next_action": "신규 진입 강도를 낮추고 후보를 압축",
            "indicator_reads": [
                {"dimension": "breadth", "label": "시장 폭", "state": "warning", "read": "시장 폭 경고 신호", "symbols": ["S5FI"]}
            ],
            "issues": [
                {"theme": "지정학", "title": "협상 신뢰도 약화", "state": "unresolved", "summary": "유가와 금리가 의심", "triggers": ["Brent 95달러"], "source_gaps": ["당사자 구속력"]}
            ],
            "watchlist_impact": {
                "growth_ai": "chase 제한",
                "cyclicals": "금리·유가 확인 후 압축",
                "energy_defense": "상대강도 관찰",
                "korea": "USDKRW·유가 부담 점검",
            },
            "data_gaps": [],
        },
        "lenses": [],
        "stocks": [],
    }

    parsed = parse_dashboard_input(payload)

    assert parsed.macro_state is not None
    assert parsed.macro_state.current_state == "fragile rally"
    assert parsed.macro_state.indicator_reads[0].label == "시장 폭"
    assert parsed.macro_state.issues[0].theme == "지정학"
    assert parsed.macro_state.watchlist_impact.growth_ai == "chase 제한"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/test_dashboard_models.py::test_parse_dashboard_input_accepts_macro_state_payload -q
```

Expected: fail with `AttributeError: 'DashboardInput' object has no attribute 'macro_state'` or parser keyword error.

- [ ] **Step 3: Add macro dataclasses and parser helpers**

Modify `dashboard/models.py` by adding these dataclasses near `MarketIndicator`:

```python
@dataclass(frozen=True)
class MacroIndicatorRead:
    dimension: str
    label: str
    state: str
    read: str
    symbols: list[str]


@dataclass(frozen=True)
class MacroIssue:
    theme: str
    title: str
    state: str
    summary: str
    triggers: list[str]
    source_gaps: list[str]


@dataclass(frozen=True)
class WatchlistImpact:
    growth_ai: str
    cyclicals: str
    energy_defense: str
    korea: str


@dataclass(frozen=True)
class MacroState:
    current_state: str
    why_it_matters: str
    next_action: str
    indicator_reads: list[MacroIndicatorRead]
    issues: list[MacroIssue]
    watchlist_impact: WatchlistImpact
    data_gaps: list[str]
```

Add `macro_state: MacroState | None = None` to `DashboardInput`.

Add this helper below `_parse_metrics`:

```python
def _parse_macro_state(payload: dict[str, Any] | None) -> MacroState | None:
    if not payload:
        return None
    impact = payload.get("watchlist_impact") or {}
    return MacroState(
        current_state=str(payload["current_state"]),
        why_it_matters=str(payload["why_it_matters"]),
        next_action=str(payload["next_action"]),
        indicator_reads=[
            MacroIndicatorRead(
                dimension=str(item["dimension"]),
                label=str(item["label"]),
                state=str(item["state"]),
                read=str(item["read"]),
                symbols=[str(value) for value in item.get("symbols", [])],
            )
            for item in payload.get("indicator_reads", [])
        ],
        issues=[
            MacroIssue(
                theme=str(item["theme"]),
                title=str(item["title"]),
                state=str(item["state"]),
                summary=str(item["summary"]),
                triggers=[str(value) for value in item.get("triggers", [])],
                source_gaps=[str(value) for value in item.get("source_gaps", [])],
            )
            for item in payload.get("issues", [])
        ],
        watchlist_impact=WatchlistImpact(
            growth_ai=str(impact.get("growth_ai", "")),
            cyclicals=str(impact.get("cyclicals", "")),
            energy_defense=str(impact.get("energy_defense", "")),
            korea=str(impact.get("korea", "")),
        ),
        data_gaps=[str(value) for value in payload.get("data_gaps", [])],
    )
```

Pass `macro_state=_parse_macro_state(payload.get("macro_state"))` when returning `DashboardInput`.

- [ ] **Step 4: Run parser test and verify GREEN**

Run:

```bash
uv run pytest tests/test_dashboard_models.py::test_parse_dashboard_input_accepts_macro_state_payload -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add dashboard/models.py tests/test_dashboard_models.py
git commit -m "Parse macro state dashboard payloads"
```

---

### Task 3: Provider And Snapshot Integration

**Files:**
- Modify: `dashboard/providers/macro.py`
- Modify: `dashboard/snapshot.py`
- Test: `tests/test_providers.py`
- Test: `tests/test_snapshot.py`

- [ ] **Step 1: Write failing provider test**

Append to `tests/test_providers.py`:

```python
from dashboard.providers import macro as macro_provider


def test_fetch_macro_includes_macro_state_from_expanded_indicators(monkeypatch):
    def fake_load_quotes(symbols):
        assert "RSP" in symbols
        assert "S5FI" in symbols
        assert "BZ=F" in symbols
        return {
            "SPY": {"price": 7600.0, "day_change_pct": 0.7, "return_pct": 3.0},
            "RSP": {"price": 180.0, "day_change_pct": -0.2, "return_pct": 0.5},
            "S5FI": {"price": 57.0, "day_change_pct": -3.0, "return_pct": -4.0},
            "^VIX": {"price": 16.2, "day_change_pct": 4.0, "return_pct": 2.0},
            "^TNX": {"price": 4.52, "day_change_pct": 1.8, "return_pct": 0.2},
            "DX-Y.NYB": {"price": 97.9, "day_change_pct": 0.1, "return_pct": 0.0},
            "GLD": {"price": 310.0, "day_change_pct": 0.4, "return_pct": 1.0},
            "BZ=F": {"price": 96.0, "day_change_pct": 1.2, "return_pct": 5.0},
        }

    monkeypatch.setattr(macro_provider, "_load_quotes", fake_load_quotes)

    payload = macro_provider.fetch_macro()

    assert payload["macro_state"]["current_state"] == "fragile rally"
    assert any(item["symbol"] == "S5FI" for item in payload["market_indicators"])
    assert any(item["symbol"] == "BZ=F" for item in payload["market_indicators"])
```

- [ ] **Step 2: Run provider test and verify RED**

Run:

```bash
uv run pytest tests/test_providers.py::test_fetch_macro_includes_macro_state_from_expanded_indicators -q
```

Expected: fail because `macro_state` is absent or expanded symbols are absent.

- [ ] **Step 3: Expand macro provider**

Modify `dashboard/providers/macro.py`:

```python
from dashboard.macro_state import build_macro_state
```

Replace `INDICATOR_SYMBOLS` with:

```python
INDICATOR_SYMBOLS: list[tuple[str, str, str]] = [
    ("SPY", "S&P 500 ETF", "미국 대형주"),
    ("RSP", "S&P 500 동일가중", "breadth"),
    ("QQQ", "Nasdaq 100 ETF", "성장주"),
    ("IWM", "Russell 2000 ETF", "breadth"),
    ("S5FI", "S&P 500 50일선 상회 비율", "breadth"),
    ("SMH", "Semiconductor ETF", "반도체"),
    ("^VIX", "변동성지수 VIX", "심리"),
    ("^TNX", "미국 10년물", "금리"),
    ("DX-Y.NYB", "달러인덱스", "환율"),
    ("USDKRW=X", "달러/원", "환율"),
    ("GLD", "금 ETF", "원자재"),
    ("BZ=F", "Brent 원유", "유가"),
]
```

Set:

```python
REGIME_SYMBOLS = ["^VIX", "^TNX", "DX-Y.NYB", "CL=F", "BZ=F", "SPY", "RSP", "S5FI"]
```

Before returning from `fetch_macro`, add:

```python
    macro_state = build_macro_state({
        "market_indicators": indicators,
        "issues": _default_issue_cards(),
    })
    return {"market_indicators": indicators, "regime": regime, "macro_state": macro_state, "errors": errors}
```

Add:

```python
def _default_issue_cards() -> list[dict]:
    return [
        {
            "theme": "지정학",
            "title": "중동 휴전 기대와 현장 충돌의 괴리",
            "state": "unresolved",
            "summary": "협상 기대는 남아 있으나 유가·금리·변동성이 종전 신뢰도를 확인해야 하는 상태.",
            "triggers": ["Brent 95달러 위 고착", "미 10년물 4.5% 재상승", "VIX 동반 상승"],
            "source_gaps": ["실시간 뉴스 자동 요약 미연결"],
        }
    ]
```

- [ ] **Step 4: Write failing snapshot test**

Append to `tests/test_snapshot.py`:

```python
from dashboard.snapshot import UniverseEntry, build_snapshot
from dashboard.providers import RawStock


def test_build_snapshot_carries_macro_state_payload():
    def fake_fetch(ticker):
        return RawStock(
            ticker=ticker,
            source="fixture",
            price=10.0,
            day_change_pct=1.0,
            pe=12.0,
            pbr=1.2,
            op_margin_pct=10.0,
            ocf_positive=True,
            roe_pct=8.0,
            revenue_growth_pct=5.0,
            op_growth_pct=6.0,
            net_flow_signal=1.0,
            ma_trend="up",
            bb_pct=0.5,
            return_pct=2.0,
            volume_ratio=1.1,
            short_ratio=None,
            as_of="2026-06-03",
            errors=[],
        )

    snapshot = build_snapshot(
        [UniverseEntry("TEST", "fixture")],
        fetch=fake_fetch,
        macro=lambda: {
            "market_indicators": [],
            "regime": {},
            "macro_state": {"current_state": "conditional", "why_it_matters": "fixture", "next_action": "fixture", "indicator_reads": [], "issues": [], "watchlist_impact": {}, "data_gaps": []},
            "errors": [],
        },
        as_of="2026-06-03",
    )

    assert snapshot["macro"]["macro_state"]["current_state"] == "conditional"
```

- [ ] **Step 5: Run snapshot test and verify behavior**

Run:

```bash
uv run pytest tests/test_snapshot.py::test_build_snapshot_carries_macro_state_payload -q
```

Expected: pass if snapshot already stores the full macro payload; fail only if code strips `macro_state`.

- [ ] **Step 6: Run provider and snapshot tests**

Run:

```bash
uv run pytest tests/test_providers.py::test_fetch_macro_includes_macro_state_from_expanded_indicators tests/test_snapshot.py::test_build_snapshot_carries_macro_state_payload -q
```

Expected: both pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add dashboard/providers/macro.py dashboard/snapshot.py tests/test_providers.py tests/test_snapshot.py
git commit -m "Include macro state in dashboard snapshots"
```

---

### Task 4: Live Overlay And Curated Issue Card

**Files:**
- Modify: `dashboard/live.py`
- Modify: `dashboard/market_insights.py` or `dashboard/sample_data.py`
- Test: `tests/test_live.py`

- [ ] **Step 1: Write failing live overlay test**

Append to `tests/test_live.py`:

```python
from dashboard.live import overlay_snapshot


def test_overlay_snapshot_adds_macro_state_to_payload():
    payload = {
        "as_of": "2026-06-03",
        "price_time": "",
        "regime": {"verdict": "conditional", "risk_appetite": "neutral", "rates": "stable", "dollar": "stable", "volatility": "low", "notes": []},
        "market_indicators": [],
        "lenses": [],
        "stocks": [],
    }
    snapshot = {
        "as_of": "2026-06-03",
        "generated_at": "2026-06-03T00:00:00+00:00",
        "macro": {
            "market_indicators": [],
            "regime": {"verdict": "conditional", "risk_appetite": "risk-on", "rates": "rising", "dollar": "stable", "volatility": "elevated", "notes": []},
            "macro_state": {
                "current_state": "fragile rally",
                "why_it_matters": "fixture",
                "next_action": "후보 압축",
                "indicator_reads": [],
                "issues": [],
                "watchlist_impact": {},
                "data_gaps": [],
            },
        },
        "stocks": {},
    }

    overlay_snapshot(payload, snapshot)

    assert payload["macro_state"]["current_state"] == "fragile rally"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/test_live.py::test_overlay_snapshot_adds_macro_state_to_payload -q
```

Expected: fail because `macro_state` is not copied into the payload.

- [ ] **Step 3: Overlay macro state**

Modify `dashboard/live.py` inside `overlay_snapshot` after regime overlay:

```python
    macro_state = macro.get("macro_state")
    if macro_state and macro_state.get("current_state"):
        payload["macro_state"] = deepcopy(macro_state)
```

- [ ] **Step 4: Run test and verify GREEN**

Run:

```bash
uv run pytest tests/test_live.py::test_overlay_snapshot_adds_macro_state_to_payload -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add dashboard/live.py tests/test_live.py
git commit -m "Overlay macro state into live dashboard input"
```

---

### Task 5: HTML And Markdown Rendering

**Files:**
- Modify: `dashboard/render.py`
- Test: `tests/test_dashboard_render.py`

- [ ] **Step 1: Write failing render test**

Append to `tests/test_dashboard_render.py`:

```python
def test_render_dashboard_html_contains_macro_state_cockpit():
    dashboard = build_dashboard(load_sample_dashboard_input())

    html = render_dashboard_html(dashboard)

    assert "현재 상태" in html
    assert "오늘의 주요 이슈" in html
    assert "시장 폭" in html
    assert "시장 심리" in html
    assert "금리" in html
    assert "환율" in html
    assert "원자재" in html
    assert "유가" in html
    assert "종목 후보 영향" in html
    assert "macro_state" not in html
    assert "Issue Card" not in html


def test_render_dashboard_markdown_contains_macro_state_brief():
    dashboard = build_dashboard(load_sample_dashboard_input())

    text = render_dashboard_markdown(dashboard)

    assert "## 매크로 현재 상태" in text
    assert "## 오늘의 주요 이슈" in text
    assert "## 종목 후보 영향" in text
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run pytest tests/test_dashboard_render.py::test_render_dashboard_html_contains_macro_state_cockpit tests/test_dashboard_render.py::test_render_dashboard_markdown_contains_macro_state_brief -q
```

Expected: fail because renderer does not output macro state cockpit labels.

- [ ] **Step 3: Add render helpers**

Modify `dashboard/render.py` with helpers:

```python
def _macro_state_html(dashboard: Dashboard) -> str:
    state = getattr(dashboard, "macro_state", None)
    if not state:
        return ""
    indicators = "\n".join(
        f'''
        <div class="mkpi">
          <div class="mkpi-label">{escape(item.label)}</div>
          <div class="mkpi-val">{escape(_macro_state_label(item.state))}</div>
          <div class="mkpi-sub neut">{escape(item.read)}</div>
        </div>'''
        for item in state.indicator_reads
    )
    issues = "\n".join(
        f'''
        <div class="hcell h-neu">
          <div class="hcell-name">{escape(issue.theme)} · {escape(issue.title)}</div>
          <div class="d-thesis">{escape(issue.summary)}</div>
          <div class="hcell-risk">주의 트리거: {escape(" · ".join(issue.triggers) or "확인 필요")}</div>
        </div>'''
        for issue in state.issues
    )
    impact = state.watchlist_impact
    return f'''
      <div class="sh"><h2>매크로 현재 상태</h2></div>
      <div class="macro-strip">
        <div class="mkpi verdict">
          <div class="mkpi-label">현재 상태</div>
          <div class="mkpi-val">{escape(_macro_current_state_label(state.current_state))}</div>
          <div class="mkpi-sub neut">{escape(state.next_action)}</div>
        </div>
        <div class="mkpi" style="min-width:360px">
          <div class="mkpi-label">왜 중요한가</div>
          <div class="mkpi-sub neut">{escape(state.why_it_matters)}</div>
        </div>
      </div>
      <div class="sh"><h2>오늘의 주요 이슈</h2></div>
      <div class="heatmap">{issues}</div>
      <div class="sh"><h2>시장 지표 판정</h2></div>
      <div class="macro-strip">{indicators}</div>
      <div class="sh"><h2>종목 후보 영향</h2></div>
      <div class="regime-notes">
        <div class="regime-note">성장/AI: {escape(impact.growth_ai)}</div>
        <div class="regime-note">경기민감: {escape(impact.cyclicals)}</div>
        <div class="regime-note">에너지/방산: {escape(impact.energy_defense)}</div>
        <div class="regime-note">한국시장: {escape(impact.korea)}</div>
      </div>
    '''


def _macro_current_state_label(value: str) -> str:
    return {
        "risk-on": "위험자산 우호",
        "conditional": "조건부",
        "risk-off": "위험 회피",
        "fragile rally": "취약한 랠리",
    }.get(value, value)


def _macro_state_label(value: str) -> str:
    return {
        "supportive": "우호",
        "warning": "경고",
        "stressed": "압박",
        "unavailable": "확인 필요",
    }.get(value, value)
```

Insert `{_macro_state_html(dashboard)}` after the first market regime section or before existing macro cards in `render_dashboard_html`.

In `render_dashboard_markdown`, after `## 시장 국면`, append:

```python
    if getattr(dashboard, "macro_state", None):
        state = dashboard.macro_state
        lines += [
            "",
            "## 매크로 현재 상태",
            f"- 현재 상태: {_macro_current_state_label(state.current_state)}",
            f"- 왜 중요한가: {state.why_it_matters}",
            f"- 다음 행동: {state.next_action}",
            "",
            "## 오늘의 주요 이슈",
        ]
        for issue in state.issues:
            lines.append(f"- {issue.theme}: {issue.title} · {issue.summary}")
        lines += [
            "",
            "## 종목 후보 영향",
            f"- 성장/AI: {state.watchlist_impact.growth_ai}",
            f"- 경기민감: {state.watchlist_impact.cyclicals}",
            f"- 에너지/방산: {state.watchlist_impact.energy_defense}",
            f"- 한국시장: {state.watchlist_impact.korea}",
        ]
```

- [ ] **Step 4: Run render tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_dashboard_render.py::test_render_dashboard_html_contains_macro_state_cockpit tests/test_dashboard_render.py::test_render_dashboard_markdown_contains_macro_state_brief -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add dashboard/render.py tests/test_dashboard_render.py
git commit -m "Render macro state cockpit"
```

---

### Task 6: End-To-End Verification

**Files:**
- Modify: `dashboard/sample_data.py` or `dashboard/market_insights.py` if fallback lacks macro state.
- Modify: `tests/test_dashboard_render.py` only if existing expectations need Korean label updates.

- [ ] **Step 1: Run focused dashboard tests**

Run:

```bash
uv run pytest tests/test_macro_state.py tests/test_dashboard_models.py tests/test_providers.py tests/test_snapshot.py tests/test_live.py tests/test_dashboard_render.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Render a local dashboard report**

Run:

```bash
uv run python scripts/render_lens_dashboard.py --output-dir state/dashboard/reports --cache-snapshot
```

Expected: command prints or creates an HTML file under `state/dashboard/reports/`.

- [ ] **Step 3: Inspect generated HTML labels**

Run:

```bash
rg "매크로 현재 상태|오늘의 주요 이슈|시장 지표 판정|종목 후보 영향|macro_state|Issue Card" state/dashboard/reports
```

Expected: Korean labels appear; raw `macro_state` and `Issue Card` do not appear.

- [ ] **Step 4: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: full suite passes. If unrelated existing tests fail, record exact failures and do not hide them.

- [ ] **Step 5: Commit final verification updates**

Run:

```bash
git status --short
git add dashboard sample_data.py tests scripts/render_lens_dashboard.py
git commit -m "Verify macro state dashboard flow"
```

Only stage files actually changed by this task. If there are unrelated dirty files, leave them unstaged.

---

## Self-Review

Spec coverage:

- Macro State Header: Task 5 renders HTML and Markdown header.
- Current Issue Cards: Task 1 derives issue cards; Task 5 renders them.
- Indicator Grid: Task 1 creates fixed dimension reads; Task 5 renders them.
- Market-To-Watchlist Impact: Task 1 derives impact; Task 5 renders it.
- Snapshot-backed freshness: Task 3 carries macro state through macro provider and snapshot.
- Error handling for missing breadth: Task 1 tests explicit gap behavior.
- Korean labels and raw term avoidance: Task 5 render tests cover primary labels and raw terms.

Placeholder scan:

- No red-flag terms or unspecified test steps remain.
- Every implementation task has a concrete test command and expected result.

Type consistency:

- Payload keys match `MacroState`, `MacroIssue`, `MacroIndicatorRead`, and `WatchlistImpact`.
- `build_macro_state()` returns dict payloads so provider/snapshot can store JSON directly.
