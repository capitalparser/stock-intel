# KRX OPEN API KR-Macro + Dual-Regime Wiring (Plan 2 / lens-dashboard 고도화)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans. 체크박스(`- [ ]`)로 추적.
>
> **BLOCKING 선행조건:** `.env`에 `KRX_API_KEY`(data.krx.co.kr OPEN API 인증키)가 있어야 Task 1~2·5 진행 가능. 없으면 Task 3·4(US series·구조)부터 시작하되 KR 라이브는 보류.
>
> **모든 명령:** `cd /Users/kjun/vault/01_Projects/04_stock_intel` 후 `uv run ...`.

**Goal:** Plan 1의 순수 듀얼 국면 엔진을 실데이터에 연결한다 — KR 매크로를 KRX OPEN API(권위) + yfinance(원화/외국인 프록시)로 조달하고, US percentile baseline(1년)을 확보하며, snapshot→live→render에 듀얼 국면을 배선하고 구 `_derive_regime`/단일 `MacroState`를 제거한다.

**Architecture:** KR 데이터 spine = **KRX OPEN API**(`data-dbg.krx.co.kr/svc/apis/`, `AUTH_KEY` 헤더). 신규 thin client(requests). KR 축(rev2): sentiment=KOSPI 실현변동성(+VKOSPI 가용 시), breadth=KOSPI vs KOSPI200 상대강도, fx=USDKRW(yfinance), flow=EWY 프록시(yfinance). percentile baseline은 KR 시리즈 캐시(또는 yfinance `^KS11` 대체). 엔진은 Plan 1의 `build_dual_regime`/`build_market_regime` 재사용 — 본 plan은 **데이터 조달 + 배선**만.

**Tech Stack:** Python 3.12, `requests`(기존 의존), yfinance(기존), Plan 1 엔진(`dashboard/percentile.py`·`macro_state.py`·`regime_history.py`·`models.py`), pytest.

**근거:** [CONTEXT.md](../../../CONTEXT.md) Macro/Dashboard Terms, [ADR-0001](../../adr/0001-macro-regime-thresholds.md)(KR 데이터 경로 rev2), Plan 1 [macro-regime-engine](2026-06-04-macro-regime-engine.md).

---

## Scope

### 포함
- `dashboard/providers/krx_openapi.py` — KRX OPEN API thin client(AUTH_KEY, 일별 지수/매매 엔드포인트)
- `dashboard/providers/kr_macro.py` — KR 4축 indicator 빌더(KRX + yfinance), graceful degradation
- `dashboard/providers/macro.py` — `_load_quotes` 1년 확장 + indicator에 `series`/`value` 추가(추가만)
- `dashboard/macro_state.py` `build_macro_state` 구간 → snapshot에서 `build_dual_regime` 호출로 교체
- `dashboard/snapshot.py` — macro payload에 `dual_regime` 임베드 + 이력 append
- `dashboard/live.py` — `dual_regime` overlay
- `dashboard/render.py` — 듀얼 국면 헤더(미국/한국) + 전이 배지·streak·whipsaw + 축 그리드(pctile)
- `dashboard/providers/macro.py` `_derive_regime` **제거** + 구 단일 `regime`/`MacroState.current_state` 렌더 경로 마이그레이션

### 비범위(다른 Plan)
- catalyst(Plan 3) / universe·KR스크린(Plan 4) / 봇 시그니처(Plan 5) / 밸류에이션 기대치(Plan 6) / 정책 렌즈(Plan 7)
- 실제 외국인 투자자별 순매수(KRX OPEN API 미제공) — v1.1
- KOSPI 전종목 %>MA breadth — 비채택(경량 프록시 사용)

---

## KRX OPEN API 사실 (Task 1에서 키로 확정)

- Base: `http://data-dbg.krx.co.kr/svc/apis/`
- 인증: 요청 헤더 `AUTH_KEY: <KRX_API_KEY>`
- 응답: JSON, 일별 데이터는 `{"OutBlock_1": [ {…}, … ]}` 형태(가설 — Task 1에서 실제 확인).
- 파라미터: 일별 엔드포인트는 `basDd=YYYYMMDD`(단일일).
- 후보 엔드포인트(Task 1에서 경로·필드 확정):
  - KOSPI 지수 일별: `idx/kospi_dd_trd` (필드 가설: `IDX_NM`, `CLSPRC_IDX`, `FLUC_RT`)
  - 파생상품지수 일별(VKOSPI 탐색): `idx/drvprod_dd_trd`
- **1년 baseline은 일별 ~250콜** → 캐시 backfill 1회 후 일별 append. 동일 KOSPI 시리즈는 yfinance `^KS11`(1콜 1년)로 baseline 대체 허용(ADR-0001).

---

## Task 1: KRX OPEN API 클라이언트 + 스키마 캡처 (BLOCKS on KRX_API_KEY)

**Files:** Create `dashboard/providers/krx_openapi.py`, `tests/fixtures/krx_kospi_dd.json`, `tests/test_krx_openapi.py`

- [ ] **Step 1: 키로 실제 응답 캡처 → fixture** (사람/구현자가 키 보유 상태에서 1회 실행)

Run:
```bash
python - <<'PY'
import os, json, urllib.request
key = os.environ["KRX_API_KEY"]
url = "http://data-dbg.krx.co.kr/svc/apis/idx/kospi_dd_trd?basDd=20260603"
req = urllib.request.Request(url, headers={"AUTH_KEY": key})
data = json.load(urllib.request.urlopen(req, timeout=20))
open("tests/fixtures/krx_kospi_dd.json", "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=2))
print(list(data.keys()))
print(data.get("OutBlock_1", [{}])[0])
PY
```
Expected: `tests/fixtures/krx_kospi_dd.json` 생성. 출력에서 **실제 키 이름**(예: `OutBlock_1`, `IDX_NM`, `CLSPRC_IDX`, `FLUC_RT`)을 확인하고, 아래 Step 3·4의 필드명을 캡처된 실제 키로 교정한다. KOSPI 종합지수 1행을 식별(예: `IDX_NM == "코스피"`).

> 필드명이 가설과 다르면 이 plan의 `_KOSPI_INDEX_NAME`/`_CLOSE_FIELD`/`_NAME_FIELD` 상수만 실제값으로 바꾼다. 나머지 로직 불변.

- [ ] **Step 2: 실패 테스트** — `tests/test_krx_openapi.py` (fixture 기반, 네트워크 없음)

```python
import json
from pathlib import Path

from dashboard.providers.krx_openapi import parse_index_daily

FIXTURE = Path(__file__).parent / "fixtures" / "krx_kospi_dd.json"


def test_parse_index_daily_extracts_kospi_close():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = parse_index_daily(payload)
    kospi = next(r for r in rows if r["name"] == "코스피")
    assert isinstance(kospi["close"], float)
    assert kospi["close"] > 0
```

- [ ] **Step 3: 실패 확인**

Run: `uv run pytest tests/test_krx_openapi.py -q`
Expected: FAIL — `ModuleNotFoundError: dashboard.providers.krx_openapi`

- [ ] **Step 4: 구현** — `dashboard/providers/krx_openapi.py` (Step 1 캡처 필드명으로 상수 교정)

```python
"""KRX OPEN API thin client (data-dbg.krx.co.kr, AUTH_KEY header).

일별 지수/매매 엔드포인트를 호출하고 OutBlock_1을 정규화한다. 인증키는
환경변수 KRX_API_KEY에서 읽는다(없으면 호출하지 않음 — graceful degradation).
"""

from __future__ import annotations

import os
from typing import Any

import requests

BASE = "http://data-dbg.krx.co.kr/svc/apis"
# Step1 캡처로 확정할 필드/값 (가설 — 실제 캡처값으로 교정).
_OUTBLOCK = "OutBlock_1"
_NAME_FIELD = "IDX_NM"
_CLOSE_FIELD = "CLSPRC_IDX"


def _float(v: Any) -> float | None:
    if v in (None, "", "-"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_index_daily(payload: dict) -> list[dict]:
    """OutBlock_1 -> [{name, close}]. 순수(네트워크 없음)."""
    rows = payload.get(_OUTBLOCK) or []
    out = []
    for r in rows:
        out.append({"name": str(r.get(_NAME_FIELD, "")), "close": _float(r.get(_CLOSE_FIELD))})
    return out


def fetch_index_daily(endpoint: str, bas_dd: str, *, key: str | None = None) -> dict:
    """raw payload. key 미설정이면 RuntimeError(상위에서 graceful degrade)."""
    key = key or os.getenv("KRX_API_KEY")
    if not key:
        raise RuntimeError("KRX_API_KEY 미설정")
    resp = requests.get(f"{BASE}/{endpoint}", params={"basDd": bas_dd},
                        headers={"AUTH_KEY": key}, timeout=20)
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 5: 통과 확인**

Run: `uv run pytest tests/test_krx_openapi.py -q`
Expected: PASS (1 passed)

- [ ] **Step 6: 커밋**

```bash
git add dashboard/providers/krx_openapi.py tests/test_krx_openapi.py tests/fixtures/krx_kospi_dd.json
git commit -m "feat(macro): KRX OPEN API thin client + index daily parse"
```

---

## Task 2: KR 시리즈 baseline 캐시 (percentile 1년)

**Files:** Create `dashboard/providers/kr_series_cache.py`, `tests/test_kr_series_cache.py`

KOSPI/KOSPI200 1년 종가 series를 캐시. v1 baseline은 **yfinance `^KS11`/`^KS200` 1콜**로 backfill(ADR-0001 허용), 당일 권위값만 KRX OPEN API로 덮어쓴다(KRX↔yf 정합). 캐시 위치 `state/dashboard/cache/krx_series/{symbol}.json` = `{"closes":[...], "as_of":"..."}`.

- [ ] **Step 1: 실패 테스트** — `tests/test_kr_series_cache.py`

```python
from dashboard.providers.kr_series_cache import load_series, save_series


def test_series_roundtrip(tmp_path):
    save_series("KOSPI", [2500.0, 2510.0, 2495.0], "2026-06-03", tmp_path)
    s = load_series("KOSPI", tmp_path)
    assert s["closes"][-1] == 2495.0
    assert s["as_of"] == "2026-06-03"


def test_load_missing_returns_none(tmp_path):
    assert load_series("NOPE", tmp_path) is None
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_kr_series_cache.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `dashboard/providers/kr_series_cache.py`

```python
"""KR index 1y close-series cache for percentile baseline."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "state" / "dashboard" / "cache" / "krx_series"


def load_series(symbol: str, cache_dir: str | Path = DEFAULT_DIR) -> dict | None:
    p = Path(cache_dir) / f"{symbol}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_series(symbol: str, closes: list[float], as_of: str, cache_dir: str | Path = DEFAULT_DIR) -> None:
    p = Path(cache_dir) / f"{symbol}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"closes": [float(c) for c in closes], "as_of": as_of},
                            ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 4: 통과 + 커밋**

Run: `uv run pytest tests/test_kr_series_cache.py -q` → PASS
```bash
git add dashboard/providers/kr_series_cache.py tests/test_kr_series_cache.py
git commit -m "feat(macro): KR index series cache for percentile baseline"
```

---

## Task 3: US macro 1년 series 확장 (percentile baseline)

**Files:** Modify `dashboard/providers/macro.py`, `tests/test_providers.py`(추가만)

`_load_quotes`를 `period="1y"`로 확장하고, 각 indicator에 `value`(현재값)와 `series`(1년 종가 리스트)를 추가한다. **기존 `regime`/`macro_state`/`market_indicators` 출력 키는 유지**(렌더는 Task 7~8에서 마이그레이션). 즉 indicator dict에 키만 추가.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_providers.py`

```python
def test_fetch_macro_indicators_carry_series(monkeypatch):
    import dashboard.providers.macro as m

    def fake_load(symbols):
        return {s: {"price": 100.0, "day_change_pct": 0.5, "return_pct": 1.0,
                    "closes": [90.0 + i for i in range(60)]} for s in symbols}

    monkeypatch.setattr(m, "_load_quotes", fake_load)
    out = m.fetch_macro()
    ind = out["market_indicators"][0]
    assert "value" in ind and "series" in ind
    assert len(ind["series"]) == 60
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_providers.py -k carry_series -q`
Expected: FAIL — KeyError `series`

- [ ] **Step 3: 구현** — `dashboard/providers/macro.py`
  - `_load_quotes`: `period="2mo"` → `period="1y"`, 반환 dict에 `"closes": closes` 추가.
  - indicator 빌드 루프에서 `"value": round(q["price"], 2)`, `"series": q.get("closes") or []` 추가(기존 키 유지).

```python
# _load_quotes 내부 out[sym] 에 closes 추가:
out[sym] = {
    "price": closes[-1],
    "day_change_pct": day_change_pct(closes),
    "return_pct": trailing_return_pct(closes, lookback=21),
    "closes": closes,
}
# yf.download(..., period="1y", ...)

# fetch_macro indicators.append(...) 에 키 추가:
indicators.append({
    "symbol": symbol, "name": name, "group": group,
    "price": round(q["price"], 2),
    "day_change_pct": round(chg, 2) if chg is not None else 0.0,
    "read": _indicator_read(symbol, group, chg),
    "value": round(q["price"], 2),
    "series": q.get("closes") or [],
})
```

- [ ] **Step 4: 통과 + 회귀**

Run: `uv run pytest tests/test_providers.py -q` → PASS (기존 포함)
Run: `uv run pytest -q` → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/providers/macro.py tests/test_providers.py
git commit -m "feat(macro): carry 1y series + value on US indicators for percentile"
```

---

## Task 4: KR macro indicator 빌더 (KRX + yfinance, graceful degradation)

**Files:** Create `dashboard/providers/kr_macro.py`, `tests/test_kr_macro.py`

`build_kr_indicators()` → `build_market_regime(..., market="KR")`이 먹는 indicator 리스트:
- `KOSPI`(지수, day_change용) + `VKOSPI`/`KOSPI_RV`(sentiment) + `KOSPI200`(breadth 짝) + `KOSPI_BREADTH`(KOSPI/KOSPI200 상대강도 0~100) + `USDKRW=X`(fx) + `FOREIGN_NET`→`EWY`(flow 프록시).
- 주입 가능한 `krx_fetch`/`yf_fetch`로 네트워크 분리(테스트는 fake 주입).
- 임의 소스 실패는 해당 indicator 제외(해당 축 unavailable로 자연 degrade).

KR symbol↔dimension 매핑은 Plan 1 `KR_SYMBOL_DIM`에 이미 있음: `KOSPI_BREADTH→breadth`, `VKOSPI/KOSPI_RV→sentiment`, `USDKRW=X→fx`, `FOREIGN_NET→flow`. 따라서 빌더는 이 심볼명으로 indicator를 emit한다. breadth는 합성 심볼 `KOSPI_BREADTH`(상대강도)로 emit.

- [ ] **Step 1: 실패 테스트** — `tests/test_kr_macro.py`

```python
from dashboard.providers.kr_macro import build_kr_indicators, realized_vol, relative_strength


def test_realized_vol_positive():
    closes = [100, 101, 99, 102, 98, 103] * 10
    assert realized_vol(closes) > 0


def test_relative_strength_band():
    # window(20) 충족 시계열. KOSPI(ret 0.08)가 KOSPI200(ret 0.06)보다 강 -> spread 0.02 -> 70.
    kospi = [100 + i * 0.4 for i in range(21)]      # u[-1]=108, u[-21]=100 -> 0.08
    kospi200 = [100 + i * 0.3 for i in range(21)]   # u[-1]=106, u[-21]=100 -> 0.06
    rs = relative_strength(kospi, kospi200)
    assert 50 < rs <= 100  # 광범위 우위 -> breadth 양호


def test_relative_strength_insufficient_data_neutral():
    # window 미충족(짧은 시계열)이면 신호 없음 = 중립 50 (데이터 부족 시 단정 안 함)
    assert relative_strength([100, 110], [100, 105]) == 50.0


def test_build_kr_indicators_shapes_for_engine():
    fake = {
        "KOSPI": {"closes": [2500.0 + i for i in range(60)], "day_change_pct": 0.4},
        "KOSPI200": {"closes": [330.0 + i * 0.1 for i in range(60)]},
        "USDKRW=X": {"closes": [1300.0 + i for i in range(60)], "value": 1359.0},
        "EWY": {"closes": [60.0 + i * 0.1 for i in range(60)], "value": 65.9},
    }
    inds = build_kr_indicators(quotes=fake)
    syms = {i["symbol"] for i in inds}
    assert "KOSPI" in syms and "KOSPI_BREADTH" in syms
    assert "USDKRW=X" in syms and "FOREIGN_NET" in syms
    for i in inds:
        assert "value" in i and "series" in i
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_kr_macro.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `dashboard/providers/kr_macro.py`

```python
"""KR macro indicators for the dual-regime engine.

KRX OPEN API(권위 지수) + yfinance(원화/외국인 프록시)를 build_market_regime용
indicator 리스트로 빚는다. quotes를 주입하면 네트워크 없이 테스트 가능.
flow는 EWY 기반 프록시(실제 투자자별 순매수는 KRX OPEN API 미제공 — v1.1).
"""

from __future__ import annotations

import math
from typing import Any


def realized_vol(closes: list[float], window: int = 20) -> float:
    use = [float(c) for c in closes[-(window + 1):] if c]
    if len(use) < 3:
        return 0.0
    rets = [use[i] / use[i - 1] - 1 for i in range(1, len(use))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(var) * math.sqrt(252) * 100  # 연율화 %


def relative_strength(kospi: list[float], kospi200: list[float], window: int = 20) -> float:
    """KOSPI vs KOSPI200 상대강도 0~100 (breadth 프록시: 광범위 KOSPI가 대형주 대비 강하면↑)."""
    def ret(s):
        u = [float(c) for c in s if c]
        if len(u) <= window:
            return 0.0
        return u[-1] / u[-window - 1] - 1
    spread = ret(kospi) - ret(kospi200)  # +면 광범위 우위(breadth 양호)
    return max(0.0, min(100.0, 50.0 + spread * 1000))  # ±5% spread -> 0..100


def _rv_series(closes: list[float], window: int = 20) -> list[float]:
    out = []
    for end in range(window + 1, len(closes) + 1):
        out.append(realized_vol(closes[:end], window))
    return out


def _rs_series(kospi: list[float], k200: list[float], window: int = 20) -> list[float]:
    n = min(len(kospi), len(k200))
    out = []
    for end in range(window + 1, n + 1):
        out.append(relative_strength(kospi[:end], k200[:end], window))
    return out


def build_kr_indicators(*, quotes: dict[str, Any]) -> list[dict]:
    inds: list[dict] = []
    kospi = quotes.get("KOSPI") or {}
    k200 = quotes.get("KOSPI200") or {}
    usdkrw = quotes.get("USDKRW=X") or {}
    ewy = quotes.get("EWY") or {}

    kc = kospi.get("closes") or []
    if kc:
        inds.append({"symbol": "KOSPI", "value": kc[-1], "series": kc,
                     "day_change_pct": kospi.get("day_change_pct", 0.0)})
        rv = _rv_series(kc)
        if rv:
            inds.append({"symbol": "KOSPI_RV", "value": rv[-1], "series": rv, "day_change_pct": 0.0})
    kc200 = k200.get("closes") or []
    if kc and kc200:
        rs = _rs_series(kc, kc200)
        if rs:
            inds.append({"symbol": "KOSPI_BREADTH", "value": rs[-1], "series": rs, "day_change_pct": 0.0})
    uc = usdkrw.get("closes") or []
    if uc:
        inds.append({"symbol": "USDKRW=X", "value": usdkrw.get("value", uc[-1]), "series": uc, "day_change_pct": 0.0})
    ec = ewy.get("closes") or []
    if ec:
        # EWY는 값↑=외국인 우호. flow 축은 RISK_LOW(값↓=위험)이므로 EWY를 그대로 쓰면 의미 일치.
        inds.append({"symbol": "FOREIGN_NET", "value": ewy.get("value", ec[-1]), "series": ec, "day_change_pct": 0.0})
    return inds


def fetch_kr_quotes() -> dict[str, Any]:
    """라이브 조달: KOSPI/KOSPI200=KRX OPEN API(권위 당일)+yfinance(1년 baseline),
    USDKRW/EWY=yfinance. 실패 소스는 dict에서 누락(상위 degrade). Task 5에서 배선."""
    raise NotImplementedError("Task 5에서 KRX+yfinance 라이브 배선")
```

> 주: `KOSPI_RV`와 `VKOSPI`는 둘 다 sentiment 축(`KR_SYMBOL_DIM`). VKOSPI 가용(Task 1에서 확인)이면 `VKOSPI` 심볼로 추가하고 RV는 생략 가능. v1은 RV로 충분.

- [ ] **Step 4: 통과 + 회귀**

Run: `uv run pytest tests/test_kr_macro.py -q` → PASS
Run: `uv run pytest -q` → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/providers/kr_macro.py tests/test_kr_macro.py
git commit -m "feat(macro): KR macro indicator builder (KRX index + EWY/USDKRW proxies)"
```

---

## Task 5: snapshot에 듀얼 국면 임베드 + 이력 append

**Files:** Modify `dashboard/snapshot.py`, `dashboard/providers/macro.py`(fetch_kr_quotes 라이브), `tests/test_snapshot.py`(추가만)

`build_snapshot`의 macro 단계에서 US indicators(Task 3) + KR indicators(Task 4)로 `build_dual_regime` 호출, 결과를 `snapshot["macro"]["dual_regime"]`에 넣고 `append_today`로 이력 기록. **기존 `regime`/`macro_state` 키는 유지**(Task 7~8 마이그레이션 전까지 렌더 호환).

- [ ] **Step 1: 실패 테스트(추가, 주입식)** — `tests/test_snapshot.py`

```python
def test_snapshot_embeds_dual_regime(tmp_path, monkeypatch):
    from dashboard import snapshot as snap

    us_inds = [{"symbol": "SPY", "value": 760.0, "series": [700.0 + i for i in range(60)], "day_change_pct": 0.5}]
    kr_inds = [{"symbol": "KOSPI", "value": 2600.0, "series": [2550.0 + i for i in range(60)], "day_change_pct": 0.3}]

    def fake_macro():
        return {"market_indicators": us_inds, "regime": {"verdict": "risk-on", "risk_appetite": "risk-on",
                "rates": "stable", "dollar": "stable", "volatility": "low", "notes": []},
                "macro_state": None, "errors": [], "_us_indicators": us_inds, "_kr_indicators": kr_inds}

    monkeypatch.setattr(snap, "_history_path", lambda: tmp_path / "regime_history.jsonl")
    out = snap.build_snapshot([], macro=fake_macro, as_of="2026-06-04")
    assert out["macro"]["dual_regime"]["us"]["regime"] in {"risk-on", "conditional", "fragile rally", "risk-off"}
    assert (tmp_path / "regime_history.jsonl").exists()
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_snapshot.py -k dual_regime -q`
Expected: FAIL — KeyError `dual_regime`

- [ ] **Step 3: 구현**
  - `providers/macro.py fetch_macro()`: US indicators(기존)에 더해 `fetch_kr_quotes()`로 KR indicators 생성, 반환 dict에 `"_us_indicators"`/`"_kr_indicators"` 추가(실패 시 빈 리스트, errors 기록). `fetch_kr_quotes` 라이브 구현(KRX OPEN API 당일 + yfinance 1년/USDKRW/EWY; 각 소스 try/except로 누락 허용).
  - `snapshot.py`: macro payload에서 us/kr indicators 꺼내 `build_dual_regime(us, kr, history=load_history(_history_path()), as_of=resolved_as_of)` 호출 → `macro_payload["dual_regime"]` 세팅 → `append_today({"as_of":..., "us":..., "kr":..., "generated_at":...}, _history_path())`. `_history_path()` 헬퍼는 `regime_history.DEFAULT_HISTORY_PATH` 반환(테스트 monkeypatch 지점).

```python
# snapshot.py
from dashboard.macro_state import build_dual_regime
from dashboard.regime_history import DEFAULT_HISTORY_PATH, append_today, load_history


def _history_path():
    return DEFAULT_HISTORY_PATH


# build_snapshot 내 macro_payload = macro() 직후:
us_inds = macro_payload.pop("_us_indicators", macro_payload.get("market_indicators", []))
kr_inds = macro_payload.pop("_kr_indicators", [])
dual = build_dual_regime(us_inds, kr_inds, history=load_history(_history_path()), as_of=resolved_as_of)
macro_payload["dual_regime"] = dual
append_today({"as_of": resolved_as_of, "us": dual["us"], "kr": dual["kr"],
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
             _history_path())
```

- [ ] **Step 4: 통과 + 회귀**

Run: `uv run pytest tests/test_snapshot.py -q` → PASS
Run: `uv run pytest -q` → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/snapshot.py dashboard/providers/macro.py tests/test_snapshot.py
git commit -m "feat(macro): embed dual_regime in snapshot + append regime history"
```

---

## Task 6: live overlay — dual_regime를 payload로

**Files:** Modify `dashboard/live.py`, `dashboard/models.py`(DashboardInput/Dashboard에 dual_regime 추가), `tests/test_dashboard_models.py`

`models.DashboardInput`/`Dashboard`에 `dual_regime: DualRegime | None` 필드 추가(기본 None — 기존 파싱 호환). `parse_dashboard_input`이 `payload.get("dual_regime")`를 `parse_dual_regime`로. `live.overlay_snapshot`이 snapshot macro의 `dual_regime`을 payload로 복사.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_dashboard_models.py`

```python
def test_parse_dashboard_input_carries_dual_regime():
    from dashboard.models import parse_dashboard_input
    payload = _minimal_dashboard_payload()  # 기존 헬퍼/픽스처 재사용
    payload["dual_regime"] = {
        "as_of": "2026-06-04",
        "us": {"market": "US", "regime": "risk-on", "why_it_matters": "", "next_action": "", "axis_reads": [], "data_gaps": []},
        "kr": {"market": "KR", "regime": "conditional", "why_it_matters": "", "next_action": "", "axis_reads": [], "data_gaps": []},
        "transitions": {"us": {"changed": False, "from": None, "to": "risk-on", "streak": 1, "whipsaw": False, "axis_changes": []},
                        "kr": {"changed": False, "from": None, "to": "conditional", "streak": 1, "whipsaw": False, "axis_changes": []}},
    }
    parsed = parse_dashboard_input(payload)
    assert parsed.dual_regime.us.regime == "risk-on"
```

> `_minimal_dashboard_payload`가 없으면 기존 `test_dashboard_models.py`의 픽스처 구성 방식을 그대로 차용한다(같은 파일 내 기존 테스트 참조).

- [ ] **Step 2: 실패 확인** → FAIL (AttributeError dual_regime)

- [ ] **Step 3: 구현**
  - `models.py`: `@dataclass DashboardInput`·`Dashboard`에 `dual_regime: DualRegime | None = None` 추가(필드 마지막, 기본값으로 호환). `parse_dashboard_input` 반환에 `dual_regime=parse_dual_regime(payload.get("dual_regime"))` 추가. `build_dashboard`(있으면)도 전달.
  - `live.py overlay_snapshot`: `macro = snapshot.get("macro") or {}` 다음에 `if macro.get("dual_regime"): payload["dual_regime"] = deepcopy(macro["dual_regime"])`.

- [ ] **Step 4: 통과 + 회귀** → `uv run pytest -q` 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/models.py dashboard/live.py tests/test_dashboard_models.py
git commit -m "feat(macro): thread dual_regime through DashboardInput/Dashboard + live overlay"
```

---

## Task 7: render — 듀얼 국면 헤더 + 전이/streak/whipsaw + 축 그리드

**Files:** Modify `dashboard/render.py`, `tests/test_dashboard_render.py`(추가만)

`dashboard.dual_regime`이 있으면 **미국 국면 / 한국 국면 2블록**을 렌더한다. 각 블록: 국면 라벨(4-state), why/next_action, 전이 배지(`어제 X → 오늘 Y` 또는 `N영업일째 {국면}`), whipsaw면 `잠정 전이 — 변동 큼`, 축 그리드(라벨·state·pctile). 한글 우선, 기계용어 노출 금지(CLAUDE.md §4.4). 구 `시장 국면`/`매크로 현재 상태` 블록은 Task 8에서 제거 — 여기서는 **dual 블록을 추가**하고 구 블록과 공존시킨 뒤 Task 8에서 구 블록을 걷어낸다.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_dashboard_render.py`

```python
def test_markdown_renders_dual_regime(dual_regime_dashboard):
    from dashboard.render import render_dashboard_markdown
    md = render_dashboard_markdown(dual_regime_dashboard)
    assert "미국 국면" in md and "한국 국면" in md
    assert "영업일째" in md or "→" in md  # streak 또는 전이 배지


def test_html_renders_dual_regime(dual_regime_dashboard):
    from dashboard.render import render_dashboard_html
    html = render_dashboard_html(dual_regime_dashboard)
    assert "한국 국면" in html
    assert "잠정 전이" in html or "영업일째" in html
```

> `dual_regime_dashboard` fixture: 기존 render 테스트의 Dashboard 생성 헬퍼에 `dual_regime`(us=risk-on streak3, kr=fragile rally whipsaw=True 전이)만 채워 구성. 같은 파일 기존 픽스처 패턴 재사용.

- [ ] **Step 2: 실패 확인** → FAIL ("미국 국면" 부재)

- [ ] **Step 3: 구현** — `dashboard/render.py`
  - markdown: `render_dashboard_markdown`에서 `if dashboard.dual_regime:` 블록 추가 — 미국/한국 각각 `_market_regime_md(mr, transition)` 헬퍼로:
    ```python
    def _regime_label_kr(regime: str) -> str:
        return {"risk-on": "위험 선호", "conditional": "조건부",
                "fragile rally": "취약한 랠리", "risk-off": "위험 회피"}[regime]

    def _transition_badge_md(t: dict) -> str:
        if t.get("changed"):
            base = f"어제 {_regime_label_kr(t['from'])} → 오늘 {_regime_label_kr(t['to'])}"
            return base + (" · 잠정 전이 — 변동 큼" if t.get("whipsaw") else "")
        return f"{t.get('streak', 1)}영업일째 {_regime_label_kr(t['to'])}"
    ```
    각 시장: 제목(`## 미국 국면`/`## 한국 국면`), `- 현재: {라벨}`, `- {전이 배지}`, `- 왜: {why}`, `- 다음: {next_action}`, 축 그리드 `- {label}: {state 한글} (pctile {pct})`.
  - html: `_dual_regime_html(dashboard)` 헬퍼로 2개 cockpit 카드(기존 `.macro-strip`/`.mkpi` 스타일 재사용) 추가, `render_dashboard_html` 본문에 삽입. whipsaw는 경고색 배지.
  - state 한글: `{"supportive":"우호","warning":"경고","stressed":"위험","unavailable":"확인 필요"}`.

- [ ] **Step 4: 통과 + 회귀** → `uv run pytest -q` 전체 그린(기존 render 테스트 유지)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/render.py tests/test_dashboard_render.py
git commit -m "feat(macro): render dual regime headers + transition/streak/whipsaw + axis grid"
```

---

## Task 8: 구 단일 국면 경로 제거 (`_derive_regime` + 구 블록)

**Files:** Modify `dashboard/providers/macro.py`, `dashboard/render.py`, `dashboard/snapshot.py`, 관련 테스트

dual_regime이 canonical이 됐으니 구 단일 경로를 걷어낸다. CONTEXT.md "국면 = 시장당 단일 canonical" 충족.

- [ ] **Step 1: 영향 grep**

Run: `grep -rn "_derive_regime\|\.regime\.verdict\|macro_state\.current_state\|dashboard.regime" dashboard/ tests/`
Expected: 사용처 목록 확보(render.py 구 블록, snapshot, providers).

- [ ] **Step 2: 구 블록 제거 + 테스트 갱신**
  - `render.py`: 구 `## 시장 국면`(verdict/risk_appetite/...) markdown 블록과 `시장 국면`/`매크로 현재 상태` HTML 블록 제거(dual로 대체됨). `_regime_value`/`_macro_current_state_html` 등 미사용 헬퍼 제거.
  - `providers/macro.py`: `_derive_regime` 및 `regime` 키 emit 제거. `macro_state`(구 단일) emit 제거. `build_macro_state` 호출 제거(있으면).
  - `snapshot.py`: macro_payload에서 구 `regime`/`macro_state` 처리 제거.
  - 구 단일 국면을 검증하던 테스트(`test_providers.py`의 regime verdict assert, `test_dashboard_render.py`의 시장 국면 블록 assert) → dual 기준으로 갱신 또는 삭제.

> 이 Task는 Plan 1의 isolation 불변식을 **의도적으로 해제**한다(이제 구 경로 제거가 목적). Plan 1에서 보존했던 `build_macro_state`/`_derive_regime`가 여기서 사라진다.

- [ ] **Step 3: 전체 회귀**

Run: `uv run pytest -q`
Expected: 전체 그린(구 단일 국면 테스트가 dual로 갱신/삭제된 상태).

- [ ] **Step 4: 커밋**

```bash
git add dashboard/ tests/
git commit -m "refactor(macro): remove single-regime path (_derive_regime, legacy blocks); dual is canonical"
```

---

## Task 9: build 스크립트 + 라이브 스모크 + 상태 라벨

**Files:** Modify `scripts/build_dashboard_snapshot.py`, `tests/test_dashboard_render.py`

- [ ] **Step 1: build 스크립트 출력 갱신** — `_derive_regime` verdict 출력(L38) 제거, dual 국면 요약 출력으로 교체:

```python
dual = snapshot["macro"].get("dual_regime", {})
print(f"US 국면: {dual.get('us', {}).get('regime', '—')} · KR 국면: {dual.get('kr', {}).get('regime', '—')}")
```

- [ ] **Step 2: 라이브 스모크** (KRX_API_KEY 보유 시)

Run: `set -a; source .env; set +a; uv run python scripts/build_dashboard_snapshot.py`
Expected: 에러 없이 snapshot 생성, `US 국면 / KR 국면` 출력. KR 소스 실패 시 축 `확인 필요`로 degrade(크래시 없음).

- [ ] **Step 3: 데이터 신선도/상태 라벨 확인** — KR이 일부 degrade면 렌더에 `확인 필요`/`프록시`(EWY) 표기되는지 HTML 육안 확인(desktop/mobile 폭, first-viewport 듀얼 국면 노출).

- [ ] **Step 4: 전체 회귀 + 커밋**

Run: `uv run pytest -q` → 전체 그린
```bash
git add scripts/build_dashboard_snapshot.py tests/
git commit -m "feat(macro): build script dual-regime summary + live smoke"
```

---

## Self-Review 체크

- **Spec coverage:** KRX OPEN API spine✓ / KR 4축 rev2(실현변동성·KOSPI/KOSPI200 breadth·USDKRW·EWY flow)✓ / US 1년 percentile baseline✓ / 듀얼 snapshot·live·render 배선✓ / 전이·streak·whipsaw 렌더✓ / _derive_regime 제거✓ / graceful degradation✓ / KRX_API_KEY .env(커밋금지)✓. 실제 외국인 순매수·VKOSPI 확정·전종목 breadth = 의도적 v1.1/비범위.
- **Placeholder scan:** KRX 응답 필드명은 Task 1에서 실제 캡처로 교정(가설 상수 표기). 그 외 placeholder 없음.
- **Type consistency:** Plan 1 계약(`build_dual_regime`/`build_market_regime`/`parse_dual_regime`/`DualRegime`) 그대로 소비. KR indicator 심볼명이 Plan 1 `KR_SYMBOL_DIM`(KOSPI_BREADTH/KOSPI_RV/USDKRW=X/FOREIGN_NET)과 일치.
- **Blocking:** Task 1·2·5 라이브·9 스모크는 `KRX_API_KEY` 필요. Task 3·4·6·7·8은 주입식 테스트라 키 없이 구현·검증 가능.

## Cross-model review 예정
Plan 1과 동일하게 (b) Codex plan 리뷰 → 차이 머지 → Codex 구현 → (a) Opus code 리뷰.

## Cross-model review 반영 v2 (2026-06-04, Codex leg) — **본 섹션이 위 태스크 본문에 우선한다**

초안 review: blocker 4 + should-fix 5 + nit 1, 전건 수용. 구현 시 아래 정정을 적용한다.

**A-01 (R-01, blocker) — 선행조건 = 키 + 서비스 승인.** KRX OPEN API는 `KRX_API_KEY` 발급 외에 **API별 활용신청 + 관리자 승인**이 별도. BLOCKING 선행조건을 `KRX_API_KEY + KOSPI 시리즈 일별시세정보 승인 + 파생상품지수 시세정보 승인`으로 명시. Task 1 캡처 실패 분류에 `unauthorized`(401), `pending_approval`, `not_subscribed`, `unknown` 추가. 승인 전이면 KR 라이브(Task 1·2·5·9)는 보류, key-free Task(3·4·6·7·8 모델부분)만 진행.

**A-02 (R-02, should-fix) — base URL.** `BASE = os.getenv("KRX_OPENAPI_BASE", "https://data-dbg.krx.co.kr/svc/apis")` (https 기본). Task 1 캡처에서 실제 최종 scheme/URL 기록.

**A-03 (R-03, blocker) — 이력 persist는 opt-in.** `build_snapshot(..., persist_regime_history: bool = False)`. 기본 False(단위테스트·dev·CI 오염 방지). `append_today`는 이 플래그가 True일 때만 호출. CLI(`scripts/build_dashboard_snapshot.py`)만 `persist_regime_history=True`로 호출. Task 5 테스트는 플래그 True + monkeypatch `_history_path`로 tmp 경로 검증, 플래그 False 기본 동작(파일 미생성)도 별도 테스트.

**A-04 (R-04, blocker) — 구 regime 제거 전 모델 마이그레이션.** Task 8 순서를 다음으로 고정:
1. `models.py`: `DashboardInput.regime: MarketRegime | None = None`, `Dashboard.regime: MarketRegime | None = None`, `macro_state: MacroState | None`(이미 Optional)로 완화. `parse_dashboard_input`이 `regime` 부재 허용(`payload.get("regime")` → None).
2. `render.py`: `dashboard.regime`/`macro_state.current_state` 직접 참조(구 markdown `## 시장 국면`, HTML verdict/regime-notes, `_regime_value`/`_macro_current_state_label`/`_macro_state_html`)를 제거하고 dual 경로로 대체. `dashboard.regime is None` 분기 방어.
3. `providers/macro.py`/`snapshot.py`: 구 `regime`/`macro_state` emit 제거.
4. grep 필수: `grep -rn "\.regime\b\|regime\.verdict\|macro_state\.current_state\|_derive_regime\|_regime_value\|_macro_current_state\|_macro_state_html" dashboard/ tests/` → 모든 참조 갱신. 깨지는 기존 테스트(test_providers regime verdict, test_dashboard_render 시장국면 블록)는 dual 기준으로 재작성/삭제.

**A-05 (R-08, blocker) — fetch_kr_quotes 구현 위치.** Task 4는 `kr_macro.py`에 `build_kr_indicators`(순수) + `fetch_kr_quotes()` **시그니처만**(NotImplementedError) 둔다. **실 구현은 Task 5**: Task 5 Files에 `dashboard/providers/kr_macro.py` 추가, `fetch_kr_quotes()`를 KRX OPEN API(KOSPI/KOSPI200 당일) + yfinance(^KS11/^KS200 1년 baseline, USDKRW=X, EWY) 라이브로 구현(각 소스 try/except로 누락 허용). `providers/macro.py`는 `from dashboard.providers.kr_macro import build_kr_indicators, fetch_kr_quotes` 후 호출만. 완료 시 NotImplementedError 잔존 금지.

**A-06 (R-06, should-fix) — series 단일 소스 + 정합 가드.** 한 percentile series는 **단일 소스로 통일**한다. KR sentiment(KOSPI 실현변동성)·breadth(KOSPI/KOSPI200)의 1년 series는 **yfinance(^KS11/^KS200)로 통일**(KRX 일별 250콜 회피). KRX OPEN API 당일 권위값은 **표시·정합검증용**으로만: `abs(krx_close/yf_last - 1) > 0.01`이면 해당 축 `unavailable` + `data_gaps`에 `KRX↔yfinance 지수 불일치` 기록(percentile series엔 KRX값을 섞지 않음). v1.1에서 KRX 단일 소스(캐시 backfill)로 전환 가능.

**A-07 (R-05, should-fix) — EWY 프록시 라벨 보존.** `build_kr_indicators`의 `FOREIGN_NET` indicator에 `"source_kind": "proxy"`, `"read": "EWY 프록시 — 실제 외국인 순매수 아님"` 포함. `build_market_regime`의 axis_reads가 indicator의 `source_kind`/proxy read를 보존하도록 확장(axis dict에 `source_kind` 전파). Task 7 render는 proxy 축에 `프록시` 배지 + 해당 read 노출(실제 순매수처럼 보이지 않게). → 이건 Plan 1 `build_market_regime` 미세 확장 필요(axis_reads에 source_kind 추가). 변경 시 Plan 1 테스트 회귀 확인.

**A-08 (R-07, should-fix) — build_dashboard가 dual_regime 전달.** Task 6에 step 추가: `build_dashboard`(존재 시, `dashboard/snapshot.py` 또는 `models.py`/`screeners.py`에서 `Dashboard(...)` 구성처)가 `dual_regime=source.dual_regime`를 전달하도록 수정. 테스트: `build_dashboard(parse_dashboard_input(payload)).dual_regime`이 None 아님을 assert. 구성처는 `grep -rn "Dashboard(" dashboard/`로 확인.

**A-09 (R-09, should-fix) — Task 5 테스트 강화.** Task 5 테스트에 US(`SPY`+`S5FI`+`^VIX`) + KR(`KOSPI`+`KOSPI_RV`+`KOSPI_BREADTH`+`USDKRW=X`+`FOREIGN_NET`) indicator를 최소 1개씩 주입하고, `dual_regime.us/kr.axis_reads`의 dimension·state·pctile, transitions, 이력 레코드 shape(`{as_of, us, kr, generated_at}`)까지 assert. false-green 방지.

**A-10 (R-10, nit) — fixture 구체화.** Task 6·7의 `_minimal_dashboard_payload`/`dual_regime_dashboard`는 plan에 완전한 코드로 제공하지 말고, 구현자가 **기존 `tests/test_dashboard_models.py`·`tests/test_dashboard_render.py`의 Dashboard 생성 픽스처를 재사용**하고 거기에 `dual_regime`만 채우라고 명시(기존 픽스처가 진실 소스). 새 픽스처를 발명하지 말 것.

## Cross-model review 반영 v3 (2026-06-05) — KRX OPEN API → yfinance ETF 피벗 (**v2보다 우선**)

KRX OPEN API가 401(개별 API 권한)로 막히고, v1 KR 경량 축엔 KRX 고유 가치가 없음을 확인. **KR spine을 yfinance ETF로 피벗** → BLOCKING(KRX_API_KEY) 제거, Task 전체 key-free. 근거 [ADR-0001 KR 데이터 경로 rev3].

- **B-01 BLOCKING 해제:** `KRX_API_KEY` 선행조건 삭제. Task 1·2(KRX 클라이언트·시리즈 캐시)는 **v1 비채택**(v1.1 옵션). A-01·A-02·A-06의 KRX 부분 무효.
- **B-02 KR 데이터(fetch_kr_quotes, Task 5):** yfinance만 사용. 심볼: KODEX200 `069500.KS`, KODEX코스닥150 `229200.KS`, `USDKRW=X`, `EWY`. 각 `period="1y"` 1콜. `^KS11`/`^KS200`은 NaN이라 금지.
- **B-03 Task 4 build_kr_indicators 조정(부호 정확성):** trend/RV leg와 breadth leg 분리.
  - `quotes["KOSPI"]` = KODEX200(069500) → `KOSPI`(trend/day_change) + `KOSPI_RV`(실현변동성) indicator.
  - breadth는 별도 leg: `quotes["KOSDAQ"]`(229200) vs `quotes["KOSPI"]`(069500) → `KOSPI_BREADTH = relative_strength(kosdaq_closes, kospi_closes)`. **leg 순서 (KOSDAQ, KOSPI)** — 코스닥 우위(risk-on/광범위)→rs↑→breadth supportive(RISK_LOW와 부호 일치). 테스트: 코스닥 outperform 시계열 → breadth state `supportive`/높은 pctile 검증.
  - `USDKRW=X`→`USDKRW=X`(fx), `EWY`→`FOREIGN_NET`(flow proxy, source_kind="proxy" 유지).
- **B-04 Task 5 snapshot:** A-03(persist_regime_history opt-in) 유지. `fetch_kr_quotes`가 yfinance 4심볼 try/except로 누락 허용(축 단위 graceful degradation). A-09 강화 테스트 유지.
- **B-05 Task 8(구 _derive_regime 제거)·Task 9(build 스모크):** 이제 key 불필요 → 정상 진행. Task 9 스모크는 yfinance 라이브로.
- **B-06 percentile baseline:** A-06 정합검증(KRX↔yfinance) 무효 — 단일 소스(yfinance) 통일이므로 series 혼합 위험 없음.

**남은 key-free 실행 순서:** Task 4 조정(B-03) → Task 5(yfinance fetch_kr_quotes + snapshot 듀얼, B-02/B-04) → Task 8(구 경로 제거) → Task 9(build 스모크).

## 다음 Plan
Plan 3 catalyst / 4 universe·KR스크린 / 5 봇 시그니처 / 6 밸류에이션 기대치(forward-pe 흡수) / 7 정책 렌즈. (v1.1: KRX OPEN API 권위값·진짜 외국인 순매수(네이버)·전종목 breadth.)
