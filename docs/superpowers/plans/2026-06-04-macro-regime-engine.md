# Macro Regime Engine Implementation Plan (Plan 1 / lens-dashboard 고도화)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **모든 명령은 프로젝트 루트에서 실행:** `cd /Users/kjun/vault/01_Projects/04_stock_intel` 후 `uv run ...`. vault root에서 pytest 실행 금지(타 프로젝트 테스트까지 수집되어 실패).

**Goal:** 단일일 절대치 국면 판정을 percentile 기반 듀얼(미국/한국) 4-state 국면 엔진으로 교체하기 위한 **순수 코어**를 추가한다 — 네트워크 없이 완전히 단위 테스트 가능.

**Architecture:** 국면 판정을 데이터 소스와 분리. 엔진은 "지표 read(현재값 + 1년 series)"를 입력받아 percentile + 절대 가드레일로 축 state를 매기고 시장별 4-state 국면을 구성한다. **Plan 1은 100% additive** — 기존 `build_macro_state`/`_derive_regime`/provider/live/render/기존 테스트를 일절 건드리지 않고 새 모듈·함수만 추가한다. 실제 KRX/yfinance fetch와 렌더·스냅샷 **교체 배선**은 Plan 2.

**Tech Stack:** Python 3.12, 기존 `dashboard/` 패키지, pytest, JSONL(이력). 추가 외부 의존 없음(Plan 1 한정).

**도메인 근거:** [CONTEXT.md](../../../CONTEXT.md) Macro/Dashboard Terms, [ADR-0001](../../adr/0001-macro-regime-thresholds.md).

**Cross-model review:** 본 plan은 Codex(GPT-5.4) 리뷰(2026-06-04, 초안 fail)를 반영한 2판이다. 정정 내역은 문서 끝 "Cross-model review 반영" 참조.

---

## Isolation 불변식 (실패 시 Plan 1 무효)

- **건드리지 않는다:** `dashboard/macro_state.py`의 기존 `build_macro_state`·`DIMENSIONS`·`SYMBOL_DIMENSION`·`_derive_regime`(providers/macro.py), `dashboard/live.py`, `dashboard/render.py`, `tests/test_macro_state.py`, `tests/test_providers.py`, `tests/test_dashboard_render.py`.
- **추가만 한다:** 새 모듈(`percentile.py`, `regime_history.py`), `macro_state.py`에 새 함수(`build_market_regime`/`build_dual_regime`), `models.py`에 새 dataclass·`parse_dual_regime`.
- **검증:** 각 태스크 후 `cd /Users/kjun/vault/01_Projects/04_stock_intel && uv run pytest -q` 전체가 **계속 그린**이어야 한다(기존 테스트 0 변경).

---

## File Structure

| 파일 | 책임 | 신규/수정 |
|---|---|---|
| `dashboard/percentile.py` | percentile_rank + 축 state 매핑(가드레일) + public severity 헬퍼. 순수. | 신규 |
| `dashboard/macro_state.py` | `build_market_regime`/`build_dual_regime` **추가**(기존 함수 유지) | 수정(추가만) |
| `dashboard/regime_history.py` | JSONL 이력 I/O + 전이 감지 | 신규 |
| `dashboard/models.py` | `AxisRead`/`MarketRegimeRead`/`RegimeTransition`/`DualRegime` + parse **추가** | 수정(추가만) |
| `tests/test_percentile.py` | percentile/state 단위 테스트 | 신규 |
| `tests/test_regime_engine.py` | build_market_regime/build_dual_regime | 신규 |
| `tests/test_regime_history.py` | 이력 I/O + 전이 | 신규 |
| `tests/test_dashboard_models.py` | 듀얼 파싱 테스트 **추가**(기존 유지) | 수정(추가만) |

---

## 핵심 계약 (시그니처 고정 — 태스크 간 일치)

```python
# dashboard/percentile.py
MIN_SERIES = 30
RISK_HIGH = "risk_up_when_high"   # 값↑ = 위험 (VIX, 금리, 유가, 달러, 원화)
RISK_LOW  = "risk_up_when_low"    # 값↓ = 위험 (breadth, 외국인 수급)
def percentile_rank(series, value) -> float | None      # [0,1]; series<MIN_SERIES면 None
def severity_rank(state: str) -> int                    # supportive0 warning1 stressed2 unavailable-1
def worse_state(a: str, b: str) -> str                  # 더 심한 state
@dataclass(frozen=True) DimensionSpec(dimension,label,direction,warn_guardrail=None,stress_guardrail=None)
def dimension_state(spec, value, series) -> str         # supportive|warning|stressed|unavailable

# dashboard/macro_state.py (추가)
def build_market_regime(indicators, *, market) -> dict
#   indicators: [{symbol,value,series:[...],day_change_pct}]
#   -> {market,regime,why_it_matters,next_action,axis_reads:[{dimension,label,state,pctile,read,symbols}],data_gaps}
def build_dual_regime(us_indicators, kr_indicators, *, history=None, as_of=None) -> dict
#   -> {as_of, us:<market_regime>, kr:<market_regime>, transitions:{us:<t>, kr:<t>}}

# dashboard/regime_history.py
DEFAULT_HISTORY_PATH = ".../state/dashboard/regime_history.jsonl"
def load_history(path=...) -> list[dict]                # 시간순
def append_today(record, path=...) -> None             # 같은 as_of 덮어쓰기
def detect_transition(history, today_market, market) -> dict
#   -> {changed,from,to,streak,whipsaw,axis_changes:[{dimension,from,to}]}
```

4-state: `"risk-on" | "conditional" | "fragile rally" | "risk-off"`.

---

## Task 1: percentile_rank + severity 헬퍼

**Files:** Create `dashboard/percentile.py`, `tests/test_percentile.py`

- [ ] **Step 1: 실패 테스트** — `tests/test_percentile.py`

```python
from dashboard.percentile import percentile_rank, severity_rank, worse_state, MIN_SERIES


def test_percentile_rank_mid():
    assert percentile_rank(list(range(100)), 50) == 0.51  # 0..50 -> 51개 <= 50


def test_percentile_rank_extremes():
    assert percentile_rank(list(range(100)), 99) == 1.0
    assert percentile_rank(list(range(100)), -5) == 0.0


def test_percentile_rank_too_short_none():
    assert percentile_rank([1.0] * (MIN_SERIES - 1), 1.0) is None


def test_percentile_rank_ignores_none():
    assert percentile_rank([None] + list(range(100)), 50) == 0.51


def test_severity_and_worse():
    assert severity_rank("stressed") > severity_rank("warning") > severity_rank("supportive")
    assert worse_state("warning", "stressed") == "stressed"
    assert worse_state("supportive", "warning") == "warning"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_percentile.py -q`
Expected: FAIL — `ModuleNotFoundError: dashboard.percentile`

- [ ] **Step 3: 구현** — `dashboard/percentile.py`

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_percentile.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/percentile.py tests/test_percentile.py
git commit -m "feat(macro): percentile_rank + severity helpers"
```

---

## Task 2: dimension_state (percentile 1급 + 절대 가드레일)

**Files:** Modify `dashboard/percentile.py`, `tests/test_percentile.py`

가드레일(ADR-0001): VIX≥20→warning, USDKRW≥1450→warning, ^TNX≥5.0→warning, Brent≥100/WTI≥95→stressed. percentile 밴드: RISK_HIGH pctile≥0.95 stressed/≥0.85 warning; RISK_LOW ≤0.05 stressed/≤0.15 warning. percentile state와 가드레일 state 중 **더 심한 것** 채택. **series 없으면**: 가드레일이 발동(warning/stressed)하면 그 state, 아니면 `"unavailable"`(가드레일 보유 여부와 무관 — 시리즈 없이 supportive로 단정하지 않음).

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_percentile.py`

```python
from dashboard.percentile import DimensionSpec, dimension_state, RISK_HIGH, RISK_LOW


def _band(center, n=60, spread=2.0):
    """center±spread 균등 60점."""
    return [center - spread + (2 * spread) * i / (n - 1) for i in range(n)]


def test_state_supportive_mid_percentile():
    spec = DimensionSpec("sentiment", "시장 심리", RISK_HIGH)
    assert dimension_state(spec, 15.0, _band(15.0)) == "supportive"


def test_state_warning_from_high_percentile():
    # 3.5..4.5 분포에서 4.40 -> 54/60=0.90 (0.85~0.95 -> warning), 가드레일 5.0 미도달
    spec = DimensionSpec("rates", "금리", RISK_HIGH, warn_guardrail=5.0)
    assert dimension_state(spec, 4.40, _band(4.0, spread=0.5)) == "warning"


def test_state_stressed_from_top_percentile():
    spec = DimensionSpec("rates", "금리", RISK_HIGH, warn_guardrail=5.0)
    assert dimension_state(spec, 4.49, _band(4.0, spread=0.5)) == "stressed"  # 0.98 >=0.95


def test_state_guardrail_forces_warning_below_percentile():
    # VIX 35±10 분포에서 21은 낮은 percentile이지만 20 가드레일이 warning 강제
    spec = DimensionSpec("sentiment", "시장 심리", RISK_HIGH, warn_guardrail=20.0)
    assert dimension_state(spec, 21.0, _band(35.0, spread=10.0)) == "warning"


def test_state_stress_guardrail():
    spec = DimensionSpec("oil", "유가", RISK_HIGH, stress_guardrail=100.0)
    assert dimension_state(spec, 101.0, _band(70.0, spread=10.0)) == "stressed"


def test_state_breadth_low_percentile_warns():
    # 40..80 분포에서 43.5 -> 6/60=0.10 (RISK_LOW 0.05~0.15 -> warning)
    spec = DimensionSpec("breadth", "시장 폭", RISK_LOW)
    assert dimension_state(spec, 43.5, _band(60.0, spread=20.0)) == "warning"


def test_state_unavailable_without_series_no_guardrail():
    spec = DimensionSpec("breadth", "시장 폭", RISK_LOW)
    assert dimension_state(spec, 50.0, []) == "unavailable"


def test_state_unavailable_without_series_guardrail_not_hit():
    spec = DimensionSpec("fx", "환율", RISK_HIGH, warn_guardrail=1450.0)
    assert dimension_state(spec, 1300.0, []) == "unavailable"  # 가드레일 미도달 -> unavailable


def test_state_guardrail_fires_without_series():
    spec = DimensionSpec("fx", "환율", RISK_HIGH, warn_guardrail=1450.0)
    assert dimension_state(spec, 1500.0, []) == "warning"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_percentile.py -q`
Expected: FAIL — `ImportError: cannot import name 'DimensionSpec'`

- [ ] **Step 3: 구현 추가** — `dashboard/percentile.py` 끝에

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_percentile.py -q`
Expected: PASS (14 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/percentile.py tests/test_percentile.py
git commit -m "feat(macro): dimension_state with percentile + absolute guardrails"
```

---

## Task 3: 시장 1개 국면 (`build_market_regime`) — macro_state 추가

**Files:** Modify `dashboard/macro_state.py`(추가만), Create `tests/test_regime_engine.py`

전 축 unavailable(사용 가능 축 0개)이면 데이터 부재이므로 `"risk-on"`이 아니라 `"conditional"`로 하강(codex should-fix #3).

- [ ] **Step 1: 실패 테스트** — `tests/test_regime_engine.py`

```python
from dashboard.macro_state import build_market_regime


def _ind(symbol, value, series, day=0.0):
    return {"symbol": symbol, "value": value, "series": series, "day_change_pct": day}


def _band(center, n=60, spread=1.0):
    return [center - spread + 2 * spread * i / (n - 1) for i in range(n)]


def test_us_fragile_rally_when_index_strong_but_breadth_warns():
    indicators = [
        _ind("SPY", 760.0, _band(720, spread=40), day=0.7),
        _ind("S5FI", 43.5, _band(60, spread=20)),     # 0.10 -> breadth warning
        _ind("^TNX", 4.40, _band(4.0, spread=0.5)),   # 0.90 -> rates warning
        _ind("^VIX", 15.0, _band(15.0, spread=2)),    # supportive
        _ind("BZ=F", 70.0, _band(70.0, spread=5)),    # supportive
    ]
    out = build_market_regime(indicators, market="US")
    assert out["market"] == "US"
    assert out["regime"] == "fragile rally"
    assert any(a["dimension"] == "breadth" and a["state"] == "warning" for a in out["axis_reads"])


def test_us_risk_on_when_all_supportive():
    indicators = [
        _ind("SPY", 760.0, _band(720, spread=40), day=0.5),
        _ind("S5FI", 70.0, _band(60, spread=20)),
        _ind("^TNX", 4.0, _band(4.0, spread=0.5)),
        _ind("^VIX", 14.0, _band(15.0, spread=2)),
        _ind("BZ=F", 68.0, _band(70.0, spread=5)),
    ]
    assert build_market_regime(indicators, market="US")["regime"] == "risk-on"


def test_all_axes_unavailable_degrades_to_conditional():
    # 대표지수만, 축 지표 없음 -> 전 축 unavailable -> conditional (risk-on 아님)
    out = build_market_regime([_ind("SPY", 760.0, _band(720, spread=40), day=0.3)], market="US")
    assert out["regime"] == "conditional"
    breadth = next(a for a in out["axis_reads"] if a["dimension"] == "breadth")
    assert breadth["state"] == "unavailable"
    assert any("breadth" in g for g in out["data_gaps"])


def test_kr_risk_off_when_fx_and_sentiment_stress():
    indicators = [
        _ind("KOSPI", 2400.0, _band(2600, spread=200), day=-1.2),
        _ind("USDKRW=X", 1500.0, _band(1350, spread=80)),  # 1.0 pctile + 1450 가드레일
        _ind("VKOSPI", 30.0, _band(20, spread=6)),         # 1.0 pctile
        _ind("KOSPI_BREADTH", 35.0, _band(55, spread=15)),
    ]
    out = build_market_regime(indicators, market="KR")
    assert out["market"] == "KR"
    assert out["regime"] == "risk-off"


def test_kr_has_no_oil_axis():
    out = build_market_regime([_ind("KOSPI", 2600.0, _band(2550, spread=80), day=0.4)], market="KR")
    assert all(a["dimension"] != "oil" for a in out["axis_reads"])
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_regime_engine.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_market_regime'`

- [ ] **Step 3: 구현 추가** — `dashboard/macro_state.py` **파일 끝에 append**(기존 코드 위에 두지 말 것)

```python
# --------------------------------------------------------------------------- #
# Dual-regime engine (ADR-0001). ADDITIVE — 기존 build_macro_state는 그대로 둔다.
# --------------------------------------------------------------------------- #
from dashboard.percentile import (  # noqa: E402
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
    "breadth": DimensionSpec("breadth", "코스피 시장 폭", RISK_LOW),
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
        worst = "supportive"
        rep_pct = None
        for it in items:
            val = _f(it.get("value"))
            if val is None:
                continue
            st = dimension_state(spec, val, it.get("series") or [])
            if rep_pct is None:
                rep_pct = percentile_rank(it.get("series") or [], val)
            if severity_rank(st) > severity_rank(worst):
                worst = st
        states[dim] = worst
        axis_reads.append({"dimension": dim, "label": spec.label, "state": worst,
                           "pctile": rep_pct, "read": _axis_read(spec.label, worst),
                           "symbols": [str(it.get("symbol")) for it in items]})

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
```

> 주: 함수 정의 뒤에 import를 두는 게 어색하면 import 블록을 `from __future__` 바로 아래(모듈 상단)로 옮겨도 된다. 기존 코드 변경 없이 import만 추가하는 것은 isolation 불변식에 위배되지 않는다.

- [ ] **Step 4: 통과 + 회귀 확인**

Run: `uv run pytest tests/test_regime_engine.py -q`
Expected: PASS (5 passed)
Run: `uv run pytest -q`
Expected: PASS (전체 그린 — 기존 테스트 0 변경)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/macro_state.py tests/test_regime_engine.py
git commit -m "feat(macro): per-market 4-state regime engine (additive)"
```

---

## Task 4: 국면 이력 I/O (`regime_history.py`)

**Files:** Create `dashboard/regime_history.py`, `tests/test_regime_history.py`

레코드 = `{"as_of","us":<market_regime>,"kr":<market_regime>,"generated_at"}`. 같은 `as_of` 덮어쓰기.

- [ ] **Step 1: 실패 테스트** — `tests/test_regime_history.py`

```python
from dashboard.regime_history import append_today, load_history


def _rec(as_of, us_regime, kr_regime):
    return {"as_of": as_of, "generated_at": f"{as_of}T00:00:00+00:00",
            "us": {"market": "US", "regime": us_regime, "axis_reads": []},
            "kr": {"market": "KR", "regime": kr_regime, "axis_reads": []}}


def test_append_and_load_roundtrip(tmp_path):
    p = tmp_path / "regime_history.jsonl"
    append_today(_rec("2026-06-02", "risk-on", "conditional"), p)
    append_today(_rec("2026-06-03", "fragile rally", "risk-off"), p)
    hist = load_history(p)
    assert [r["as_of"] for r in hist] == ["2026-06-02", "2026-06-03"]
    assert hist[-1]["us"]["regime"] == "fragile rally"


def test_same_day_overwrites(tmp_path):
    p = tmp_path / "regime_history.jsonl"
    append_today(_rec("2026-06-03", "risk-on", "risk-on"), p)
    append_today(_rec("2026-06-03", "conditional", "risk-off"), p)
    hist = load_history(p)
    assert len(hist) == 1
    assert hist[0]["us"]["regime"] == "conditional"


def test_load_missing_returns_empty(tmp_path):
    assert load_history(tmp_path / "nope.jsonl") == []
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_regime_history.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `dashboard/regime_history.py`

```python
"""Dual-regime daily history (JSONL, one record per business day) + transitions."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_HISTORY_PATH = (
    Path(__file__).resolve().parents[1] / "state" / "dashboard" / "regime_history.jsonl"
)


def load_history(path: str | Path = DEFAULT_HISTORY_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    records = [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]
    records.sort(key=lambda r: r.get("as_of", ""))
    return records


def append_today(record: dict, path: str | Path = DEFAULT_HISTORY_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = {r["as_of"]: r for r in load_history(p)}
    existing[record["as_of"]] = record  # same day overwrite
    ordered = [existing[k] for k in sorted(existing)]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ordered) + "\n", encoding="utf-8")
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_regime_history.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/regime_history.py tests/test_regime_history.py
git commit -m "feat(macro): dual-regime JSONL history (same-day overwrite)"
```

---

## Task 5: 전이 감지 (`detect_transition`)

**Files:** Modify `dashboard/regime_history.py`, `tests/test_regime_history.py`

streak = **연속 저장 레코드** 기준(오늘 포함). whipsaw = 전이 발생이고 직전 streak ≤ 1. axis_changes = 양쪽 모두 실측 state(unavailable 아님)인 축의 변화만(가용성 변화 노이즈 제외, codex should-fix #4).

> **v1 한계(문서화):** streak은 `as_of` 달력 연속성을 검증하지 않고 "연속 저장 레코드"로 정의한다. 일일 runner 전제상 영업일과 실질 동등. 장기 gap을 streak에서 끊는 calendar-aware 처리는 Plan 2+ 이연.

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_regime_history.py`

```python
from dashboard.regime_history import detect_transition


def _mkt(regime, axis_states=None):
    axis_states = axis_states or {}
    return {"market": "US", "regime": regime,
            "axis_reads": [{"dimension": d, "label": d, "state": s} for d, s in axis_states.items()]}


def test_transition_changed_with_axis_changes():
    prev = {"as_of": "2026-06-02", "us": _mkt("risk-on", {"breadth": "supportive", "rates": "supportive"})}
    today = _mkt("fragile rally", {"breadth": "warning", "rates": "supportive"})
    t = detect_transition([prev], today, "us")
    assert t["changed"] is True
    assert t["from"] == "risk-on"
    assert t["to"] == "fragile rally"
    assert {"dimension": "breadth", "from": "supportive", "to": "warning"} in t["axis_changes"]


def test_transition_streak_counts_consecutive():
    hist = [{"as_of": "2026-06-01", "us": _mkt("risk-on")},
            {"as_of": "2026-06-02", "us": _mkt("risk-on")}]
    t = detect_transition(hist, _mkt("risk-on"), "us")
    assert t["changed"] is False
    assert t["streak"] == 3


def test_transition_whipsaw_when_prior_streak_short():
    hist = [{"as_of": "2026-06-01", "us": _mkt("risk-on")},
            {"as_of": "2026-06-02", "us": _mkt("fragile rally")}]  # prior streak 1
    t = detect_transition(hist, _mkt("risk-off"), "us")
    assert t["changed"] is True
    assert t["whipsaw"] is True


def test_axis_changes_excludes_availability_noise():
    prev = {"as_of": "2026-06-02", "us": _mkt("conditional", {"breadth": "unavailable"})}
    today = _mkt("conditional", {"breadth": "warning"})
    t = detect_transition([prev], today, "us")
    assert t["axis_changes"] == []  # unavailable -> warning은 시그널 아님


def test_transition_no_history():
    t = detect_transition([], _mkt("risk-on"), "us")
    assert t["changed"] is False
    assert t["from"] is None
    assert t["streak"] == 1
    assert t["whipsaw"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_regime_history.py -q`
Expected: FAIL — `ImportError: cannot import name 'detect_transition'`

- [ ] **Step 3: 구현 추가** — `dashboard/regime_history.py` 끝에

```python
def _axis_states(market_record: dict) -> dict[str, str]:
    return {a["dimension"]: a["state"] for a in market_record.get("axis_reads", [])}


def detect_transition(history: list[dict], today_market: dict, market: str) -> dict:
    """`history`: 오늘을 제외한 이전 레코드들. `market` in {'us','kr'}."""
    prior = [r for r in history if market in r]
    to_regime = today_market["regime"]
    if not prior:
        return {"changed": False, "from": None, "to": to_regime,
                "streak": 1, "whipsaw": False, "axis_changes": []}

    prev = prior[-1][market]
    from_regime = prev.get("regime")
    changed = from_regime != to_regime

    prior_streak = 0
    for r in reversed(prior):
        if r[market].get("regime") == from_regime:
            prior_streak += 1
        else:
            break
    streak = 1 if changed else prior_streak + 1
    whipsaw = changed and prior_streak <= 1

    prev_axis = _axis_states(prev)
    today_axis = _axis_states(today_market)
    axis_changes = [
        {"dimension": d, "from": prev_axis[d], "to": today_axis[d]}
        for d in today_axis
        if prev_axis.get(d) not in (None, "unavailable")
        and today_axis[d] != "unavailable"
        and prev_axis[d] != today_axis[d]
    ]
    return {"changed": changed, "from": from_regime, "to": to_regime,
            "streak": streak, "whipsaw": whipsaw, "axis_changes": axis_changes}
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_regime_history.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/regime_history.py tests/test_regime_history.py
git commit -m "feat(macro): transition detection (streak + whipsaw, availability noise filtered)"
```

---

## Task 6: 듀얼 결합 (`build_dual_regime`)

**Files:** Modify `dashboard/macro_state.py`(추가만), `tests/test_regime_engine.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_regime_engine.py`

```python
from dashboard.macro_state import build_dual_regime


def test_build_dual_regime_attaches_transitions():
    us = [_ind("SPY", 760.0, _band(720, spread=40), day=0.5),
          _ind("S5FI", 70.0, _band(60, spread=20)),
          _ind("^VIX", 14.0, _band(15.0, spread=2))]
    kr = [_ind("KOSPI", 2600.0, _band(2550, spread=80), day=0.4),
          _ind("USDKRW=X", 1300.0, _band(1350, spread=80)),
          _ind("VKOSPI", 16.0, _band(20, spread=6))]
    history = [{"as_of": "2026-06-03",
                "us": {"market": "US", "regime": "conditional", "axis_reads": []},
                "kr": {"market": "KR", "regime": "risk-on", "axis_reads": []}}]
    out = build_dual_regime(us, kr, history=history, as_of="2026-06-04")
    assert out["as_of"] == "2026-06-04"
    assert out["us"]["regime"] == "risk-on"
    assert out["transitions"]["us"]["changed"] is True
    assert out["transitions"]["us"]["from"] == "conditional"
    assert out["transitions"]["kr"]["changed"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_regime_engine.py::test_build_dual_regime_attaches_transitions -q`
Expected: FAIL — `ImportError: cannot import name 'build_dual_regime'`

- [ ] **Step 3: 구현 추가** — `dashboard/macro_state.py` 끝에

```python
from dashboard.regime_history import detect_transition  # noqa: E402


def build_dual_regime(us_indicators, kr_indicators, *, history=None, as_of=None) -> dict:
    history = history or []
    us = build_market_regime(us_indicators, market="US")
    kr = build_market_regime(kr_indicators, market="KR")
    return {"as_of": as_of, "us": us, "kr": kr,
            "transitions": {"us": detect_transition(history, us, "us"),
                            "kr": detect_transition(history, kr, "kr")}}
```

- [ ] **Step 4: 통과 + 회귀**

Run: `uv run pytest tests/test_regime_engine.py -q`
Expected: PASS (6 passed)
Run: `uv run pytest -q`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/macro_state.py tests/test_regime_engine.py
git commit -m "feat(macro): build_dual_regime combining US/KR + transitions"
```

---

## Task 7: 모델 — 듀얼/전이 dataclass + parse (추가만)

**Files:** Modify `dashboard/models.py`(추가만), `tests/test_dashboard_models.py`(추가만)

기존 dataclass/`parse_dashboard_input` 불변. 새 타입만 추가.

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_dashboard_models.py`

```python
from dashboard.models import parse_dual_regime, DualRegime


def test_parse_dual_regime():
    payload = {
        "as_of": "2026-06-04",
        "us": {"market": "US", "regime": "fragile rally", "why_it_matters": "…",
               "next_action": "후보 압축",
               "axis_reads": [{"dimension": "breadth", "label": "시장 폭",
                               "state": "warning", "pctile": 0.1, "read": "…", "symbols": ["S5FI"]}],
               "data_gaps": []},
        "kr": {"market": "KR", "regime": "risk-off", "why_it_matters": "…",
               "next_action": "방어 전환 감시", "axis_reads": [], "data_gaps": ["원화"]},
        "transitions": {
            "us": {"changed": True, "from": "risk-on", "to": "fragile rally",
                   "streak": 1, "whipsaw": True, "axis_changes": []},
            "kr": {"changed": False, "from": "risk-off", "to": "risk-off",
                   "streak": 3, "whipsaw": False, "axis_changes": []}}}
    dual = parse_dual_regime(payload)
    assert isinstance(dual, DualRegime)
    assert dual.us.regime == "fragile rally"
    assert dual.us.axis_reads[0].state == "warning"
    assert dual.transitions["us"].whipsaw is True
    assert dual.transitions["kr"].streak == 3
    assert dual.transitions["us"].from_regime == "risk-on"
    assert dual.kr.data_gaps == ["원화"]


def test_parse_dual_regime_none():
    assert parse_dual_regime(None) is None
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_dashboard_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'parse_dual_regime'`

- [ ] **Step 3: 구현 추가** — `dashboard/models.py` 끝에

```python
@dataclass(frozen=True)
class AxisRead:
    dimension: str
    label: str
    state: str
    pctile: float | None
    read: str
    symbols: list[str]


@dataclass(frozen=True)
class MarketRegimeRead:
    market: str
    regime: str
    why_it_matters: str
    next_action: str
    axis_reads: list[AxisRead]
    data_gaps: list[str]


@dataclass(frozen=True)
class RegimeTransition:
    changed: bool
    to: str
    streak: int
    whipsaw: bool
    from_regime: str | None
    axis_changes: list[dict]


@dataclass(frozen=True)
class DualRegime:
    as_of: str | None
    us: MarketRegimeRead
    kr: MarketRegimeRead
    transitions: dict[str, RegimeTransition]


def _parse_market_regime(payload: dict[str, Any]) -> MarketRegimeRead:
    return MarketRegimeRead(
        market=str(payload["market"]),
        regime=str(payload["regime"]),
        why_it_matters=str(payload.get("why_it_matters", "")),
        next_action=str(payload.get("next_action", "")),
        axis_reads=[
            AxisRead(
                dimension=str(a["dimension"]), label=str(a["label"]), state=str(a["state"]),
                pctile=(None if a.get("pctile") is None else float(a["pctile"])),
                read=str(a.get("read", "")), symbols=[str(s) for s in a.get("symbols", [])],
            )
            for a in payload.get("axis_reads", [])
        ],
        data_gaps=[str(g) for g in payload.get("data_gaps", [])],
    )


def _parse_transition(payload: dict[str, Any]) -> RegimeTransition:
    return RegimeTransition(
        changed=bool(payload["changed"]), to=str(payload["to"]),
        streak=int(payload["streak"]), whipsaw=bool(payload["whipsaw"]),
        from_regime=(None if payload.get("from") is None else str(payload["from"])),
        axis_changes=[dict(c) for c in payload.get("axis_changes", [])],
    )


def parse_dual_regime(payload: dict[str, Any] | None) -> DualRegime | None:
    if not payload:
        return None
    return DualRegime(
        as_of=(None if payload.get("as_of") is None else str(payload["as_of"])),
        us=_parse_market_regime(payload["us"]),
        kr=_parse_market_regime(payload["kr"]),
        transitions={k: _parse_transition(v) for k, v in (payload.get("transitions") or {}).items()},
    )
```

- [ ] **Step 4: 통과 + 전체 회귀**

Run: `uv run pytest tests/test_dashboard_models.py -q`
Expected: PASS
Run: `uv run pytest -q`
Expected: PASS (전체 그린)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/models.py tests/test_dashboard_models.py
git commit -m "feat(macro): DualRegime / RegimeTransition models + parser (additive)"
```

---

## Self-Review 체크

- **Spec coverage:** percentile(ADR-0001)✓ / 듀얼 국면✓ / 가드레일 VIX20·USDKRW1450·금리5.0·유가100✓ / 이력 JSONL 하루1레코드 듀얼✓ / 전이 3층위+whipsaw✓. KR 실데이터 fetch·렌더·스냅샷·`_derive_regime` 제거는 Plan 2.
- **Isolation:** 전 태스크가 additive. 기존 `build_macro_state`/provider/live/render/기존 테스트 0 변경. 각 주요 태스크 후 `uv run pytest -q` 전체 그린 게이트.
- **Type consistency:** `build_market_regime`/`build_dual_regime`/`detect_transition`/`parse_dual_regime` 시그니처 일치. 전이 dict 키(`changed/from/to/streak/whipsaw/axis_changes`) Task5↔6↔7 일치. `RegimeTransition.from_regime`은 payload `from` 매핑.
- **Placeholder scan:** 없음.

## Cross-model review 반영 (2026-06-04, Codex GPT-5.4 leg)

초안 fail → 2판에서 정정:
- **[blocker] 격리 위반** → Plan 1 전면 additive 재구성. `build_macro_state`/`_derive_regime`/기존 테스트 불변. 신규 테스트는 `test_regime_engine.py`로 분리.
- **[blocker] 4.49 percentile=stressed** → Task2 테스트 값 4.40(warning)/4.49(stressed 별도) 분리, breadth 43.5(warning)로 수정.
- **[should-fix] 전 축 unavailable→risk-on** → `_compose_regime`이 conditional로 하강 + 테스트.
- **[should-fix] axis_changes 가용성 노이즈** → unavailable 관여 전이 필터 + 테스트.
- **[should-fix] dimension_state series-없음 분기** → 가드레일 미도달 시 unavailable(중첩 삼항 제거).
- **[should-fix] _SEVERITY cross-module** → public `severity_rank`/`worse_state`.
- **[doc] streak 영업일 gap** → "연속 저장 레코드" 정의 명시, calendar-aware Plan 2+ 이연.
- **[doc] pytest cwd** → 프로젝트 루트 실행 명시.
- **[doc] percentile 밴드** → ADR-0001에 ratify(별도 커밋).

## 다음 Plan
- **Plan 2:** KR KRX provider(외국인순매수/원화/VKOSPI/breadth) + 1년 series + snapshot/live/render 듀얼 배선 + `_derive_regime` 제거 + `.env` KRX_ID/PW + 축단위 graceful degradation.
- Plan 3 catalyst / 4 universe·KR스크린 / 5 봇 시그니처 / 6 밸류에이션 기대치(forward-pe 흡수) / 7 정책 렌즈.
