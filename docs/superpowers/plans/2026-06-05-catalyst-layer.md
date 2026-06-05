# Catalyst Layer — 종목 시간축 이벤트 (Plan 3 / lens-dashboard 고도화)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans. 체크박스로 추적.
>
> **모든 명령:** `cd /Users/kjun/vault/01_Projects/04_stock_intel` 후 `uv run ...`.

**Goal:** 후보 카드에 **시간축 catalyst**를 붙인다 — KR은 **최근 공급계약**(DART 단일판매·공급계약체결, 공시검색 list.json), US는 **다가오는 실적발표일**(yfinance). `다가오는 catalyst: 실적 D-12`, `최근 catalyst: 공급계약 5/28` 형태로 표기.

**Architecture:** 새 `dashboard/providers/catalyst.py`가 ticker별 catalyst 리스트를 만든다(KR=DART list.json 공급계약, US=yfinance 실적일). 기존 `data.fundamental._find_corp_code`(corp_code 해소)·DART_API_KEY 재사용. snapshot이 injectable catalyst fetch로 carry, live가 후보에 주입, render가 카드에 표기. 전부 graceful degrade(키/네트워크 없으면 빈 리스트).

**Tech Stack:** Python 3.12, requests(기존), yfinance(기존), 기존 `dashboard/`·`data/` 패키지, pytest. DART_API_KEY는 선택(미설정 시 KR catalyst 빈 리스트). 추가 외부 의존 없음.

**근거:** [CONTEXT.md](../../../CONTEXT.md) `catalyst (Catalyst)` 용어, Plan 4·5(머지됨).

---

## Scope

### 포함
- `dashboard/providers/catalyst.py` 신규 — `fetch_catalysts(ticker)` (KR=DART 공급계약, US=yfinance 실적일) + 순수 helper(`_supply_contract_catalysts`, `_days_until`).
- `dashboard/models.py` — `StockInput`/`Candidate`에 `catalysts: list[dict]` 필드(추가, 기본 빈 리스트).
- `dashboard/snapshot.py` — injectable catalyst fetch + stock dict carry.
- `dashboard/live.py` — catalysts 주입 + evidence 한 줄.
- `dashboard/render.py` — 카드에 `다가오는/최근 catalyst` 표기(md+html).
- 테스트.

### 비범위 (다른 Plan / v1.1)
- **KR 다가오는 실적발표일**: 무료 forward 소스 부재 → v1.1(네이버 종목일정 등). v1 KR catalyst = 최근 공급계약(backward)만.
- 락업해제·지수편입·배당락 → 후속.
- 밸류에이션 기대치(Plan 6) / 정책 렌즈(Plan 7).

---

## catalyst dict 계약 (확정)

```python
{
  "type": "earnings" | "supply_contract",
  "direction": "upcoming" | "recent",
  "date": "YYYY-MM-DD",
  "days": int,            # upcoming: D-n(양수), recent: 경과일(양수). 없으면 생략.
  "label": str,           # 화면 문구: "실적 D-12", "공급계약 (5/28)"
  "detail": str,          # 보조(공급계약 상대/금액 등, 있으면)
}
```

KR 공급계약 source = DART 공시검색 `https://opendart.fss.or.kr/api/list.json`
params: `crtfc_key`, `corp_code`, `bgn_de`(YYYYMMDD, 최근 90일), `end_de`, `page_count=100`.
응답 `{"status","message","list":[{"report_nm","rcept_dt"(YYYYMMDD),"rcept_no","flr_nm",...}]}`.
필터: `report_nm`에 `공급계약` 포함. status != "000"이면 빈 리스트(graceful).

---

## File Structure

| 파일 | 책임 | 신규/수정 |
|---|---|---|
| `dashboard/providers/catalyst.py` | catalyst fetch(KR DART/US yfinance) + 순수 helper | 신규 |
| `dashboard/models.py` | StockInput/Candidate catalysts 필드 | 수정(추가) |
| `dashboard/snapshot.py` | catalyst carry(injectable) | 수정 |
| `dashboard/live.py` | catalysts 주입 + evidence | 수정 |
| `dashboard/render.py` | 카드 catalyst 표기 | 수정 |
| tests/test_catalyst.py 외 | | 신규/수정 |

---

## 핵심 계약 (시그니처 고정)

```python
# dashboard/providers/catalyst.py
def _days_until(date_str: str, today: str) -> int            # 순수: (date - today) 일수(음수 가능)
def _supply_contract_catalysts(dart_list: list[dict], today: str) -> list[dict]   # 순수: list.json -> catalysts
def fetch_catalysts(ticker: str, *, today: str | None = None) -> list[dict]
#   KR(6자리)=DART 공급계약(최근), US=yfinance 실적일(다가오는). 실패/키없음 -> [].
```

`today` 주입 가능(테스트 결정성; 기본은 호출 시점 — 단 `datetime.now`는 호출부에서만, 순수 helper엔 today 전달).

---

## Task 1: 순수 helper (날짜·공급계약 파싱)

**Files:** Create `dashboard/providers/catalyst.py`, `tests/test_catalyst.py`

- [ ] **Step 1: 실패 테스트** — `tests/test_catalyst.py`

```python
from dashboard.providers.catalyst import _days_until, _supply_contract_catalysts


def test_days_until_future_and_past():
    assert _days_until("2026-06-17", "2026-06-05") == 12
    assert _days_until("2026-05-28", "2026-06-05") == -8


def test_supply_contract_catalysts_filters_and_shapes():
    dart_list = [
        {"report_nm": "단일판매ㆍ공급계약체결", "rcept_dt": "20260528", "flr_nm": "삼성전자"},
        {"report_nm": "분기보고서", "rcept_dt": "20260515", "flr_nm": "삼성전자"},
        {"report_nm": "[정정]단일판매ㆍ공급계약체결", "rcept_dt": "20260601", "flr_nm": "삼성전자"},
    ]
    out = _supply_contract_catalysts(dart_list, "2026-06-05")
    assert len(out) == 2  # 공급계약 2건만(분기보고서 제외)
    first = out[0]  # 최신순
    assert first["type"] == "supply_contract"
    assert first["direction"] == "recent"
    assert first["date"] == "2026-06-01"
    assert "공급계약" in first["label"]
    assert first["days"] == 4  # 경과 4일


def test_supply_contract_empty_when_none():
    assert _supply_contract_catalysts([], "2026-06-05") == []
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_catalyst.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `dashboard/providers/catalyst.py`

```python
"""Catalyst layer: per-ticker time-axis events (Plan 3).

KR(6자리)=DART 공시검색 단일판매ㆍ공급계약체결(최근), US=yfinance 실적일(다가오는).
DART_API_KEY/yfinance 미가용 시 graceful degrade(빈 리스트). 순수 helper는
``today``를 주입받아 결정적이다.
"""

from __future__ import annotations

import os
from datetime import date, datetime

import requests

from dashboard.providers.base import classify_market

_DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"


def _days_until(date_str: str, today: str) -> int:
    d = date.fromisoformat(date_str)
    t = date.fromisoformat(today)
    return (d - t).days


def _fmt(yyyymmdd: str) -> str:
    return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _supply_contract_catalysts(dart_list: list[dict], today: str) -> list[dict]:
    rows = [r for r in dart_list if "공급계약" in str(r.get("report_nm", ""))]
    rows.sort(key=lambda r: str(r.get("rcept_dt", "")), reverse=True)
    out: list[dict] = []
    for r in rows:
        raw = str(r.get("rcept_dt", ""))
        if len(raw) != 8:
            continue
        d = _fmt(raw)
        elapsed = -_days_until(d, today)  # 경과일(양수)
        out.append({
            "type": "supply_contract",
            "direction": "recent",
            "date": d,
            "days": elapsed,
            "label": f"공급계약 ({int(d[5:7])}/{int(d[8:10])})",
            "detail": str(r.get("flr_nm", "")),
        })
    return out


def fetch_catalysts(ticker: str, *, today: str | None = None) -> list[dict]:
    today = today or date.today().isoformat()
    market = classify_market(ticker)
    if market == "KR":
        return _fetch_kr_supply_contracts(ticker, today)
    return _fetch_us_earnings(ticker, today)


def _fetch_kr_supply_contracts(ticker: str, today: str) -> list[dict]:
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        return []
    try:
        from data.fundamental import _find_corp_code

        corp_code = _find_corp_code(api_key, ticker)
        if not corp_code:
            return []
        bgn = (date.fromisoformat(today).replace(day=1)).strftime("%Y%m%d")  # 보수적; 아래서 90일로 확장
        bgn = _minus_days(today, 90)
        resp = requests.get(_DART_LIST_URL, params={
            "crtfc_key": api_key, "corp_code": corp_code,
            "bgn_de": bgn, "end_de": today.replace("-", ""), "page_count": 100,
        }, timeout=20)
        data = resp.json()
        if data.get("status") != "000":
            return []
        return _supply_contract_catalysts(data.get("list") or [], today)
    except Exception:  # pragma: no cover - network/degrade
        return []


def _fetch_us_earnings(ticker: str, today: str) -> list[dict]:
    try:
        import yfinance as yf

        cal = yf.Ticker(ticker).calendar
        next_date = _extract_earnings_date(cal)
        if not next_date:
            return []
        days = _days_until(next_date, today)
        if days < 0:
            return []
        return [{
            "type": "earnings", "direction": "upcoming", "date": next_date,
            "days": days, "label": f"실적 D-{days}", "detail": "",
        }]
    except Exception:  # pragma: no cover - network/degrade
        return []


def _extract_earnings_date(cal) -> str | None:
    # yfinance 2.x: calendar는 dict, 'Earnings Date'가 [date, ...]. 방어적으로 파싱.
    try:
        val = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if not val:
            return None
        first = val[0] if isinstance(val, (list, tuple)) else val
        if isinstance(first, datetime):
            return first.date().isoformat()
        if isinstance(first, date):
            return first.isoformat()
        return date.fromisoformat(str(first)[:10]).isoformat()
    except Exception:
        return None


def _minus_days(today: str, n: int) -> str:
    from datetime import timedelta

    return (date.fromisoformat(today) - timedelta(days=n)).strftime("%Y%m%d")
```

> 주: `_fetch_kr_supply_contracts`의 `bgn` 첫 줄(replace day=1)은 오타 잔재 — 구현 시 `bgn = _minus_days(today, 90)` 한 줄만 남길 것(테스트가 순수 helper만 보므로 영향 없으나 정리).

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_catalyst.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/providers/catalyst.py tests/test_catalyst.py
git commit -m "feat(catalyst): KR supply-contract + US earnings catalyst provider"
```

---

## Task 2: 모델 — catalysts 필드

**Files:** Modify `dashboard/models.py`, `tests/test_dashboard_models.py`

`StockInput`/`Candidate`에 `catalysts: list[dict] | None = None` 추가(기본값, 기존 호환). `parse_dashboard_input`이 `[dict(c) for c in item.get("catalysts", [])]`.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_dashboard_models.py`

```python
def test_parse_stock_carries_catalysts():
    from dashboard.models import parse_dashboard_input
    payload = _minimal_payload_one_stock(catalysts=[
        {"type": "earnings", "direction": "upcoming", "date": "2026-06-17", "days": 12, "label": "실적 D-12"}])
    s = parse_dashboard_input(payload).stocks[0]
    assert s.catalysts[0]["label"] == "실적 D-12"
```

> `_minimal_payload_one_stock`은 기존 test_dashboard_models.py의 인라인 payload 패턴으로 새로 작성(없는 헬퍼 import 금지). stock 하나에 `catalysts`만 추가.

- [ ] **Step 2: 실패 확인** → FAIL (AttributeError catalysts)

- [ ] **Step 3: 구현** — `dashboard/models.py`
  - `StockInput`: `catalysts: list[dict] | None = None`. `Candidate`: `catalysts: list[dict]`(또는 None 기본; 끝 필드).
  - `parse_dashboard_input` StockInput 생성에 `catalysts=[dict(c) for c in item.get("catalysts", [])]`.
  - `screeners._build_candidate`가 `catalysts=stock.catalysts or []` 전달.

- [ ] **Step 4: 통과 + 회귀** → `uv run pytest -q` 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/models.py dashboard/screeners.py tests/test_dashboard_models.py
git commit -m "feat(catalyst): catalysts field on StockInput/Candidate"
```

---

## Task 3: snapshot carry (injectable)

**Files:** Modify `dashboard/snapshot.py`, `tests/test_snapshot.py`

`build_snapshot(..., catalysts: Callable[[str], list[dict]] = fetch_catalysts)`. 각 stock dict에 `"catalysts": catalysts(ticker)`(try/except degrade → []).

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_snapshot.py`

```python
def test_snapshot_carries_catalysts():
    from dashboard.snapshot import build_snapshot, UniverseEntry
    from dashboard.providers.base import RawStock
    snap = build_snapshot(
        [UniverseEntry("000660", "반도체")],
        fetch=lambda t: RawStock("000660", "KR", price=210000),
        macro=lambda: {"market_indicators": [], "errors": []},
        catalysts=lambda t: [{"type": "supply_contract", "direction": "recent",
                              "date": "2026-06-01", "days": 4, "label": "공급계약 (6/1)"}],
        as_of="2026-06-05",
    )
    assert snap["stocks"]["000660"]["catalysts"][0]["label"] == "공급계약 (6/1)"
```

- [ ] **Step 2: 실패 확인** → FAIL (KeyError catalysts)

- [ ] **Step 3: 구현** — `dashboard/snapshot.py`
  - import `from dashboard.providers.catalyst import fetch_catalysts`.
  - `build_snapshot(..., catalysts: Callable[[str], list[dict]] = fetch_catalysts)`.
  - stock dict에 `"catalysts": _safe_catalysts(catalysts, ticker)`(try/except → []).

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/snapshot.py tests/test_snapshot.py
git commit -m "feat(catalyst): snapshot carries per-ticker catalysts"
```

---

## Task 4: live overlay 주입

**Files:** Modify `dashboard/live.py`, `tests/test_live.py`

`_overlay_stock`이 snapshot `catalysts`를 stock으로 복사 + evidence 한 줄(가장 임박/최신 1건).

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_live.py`

```python
def test_overlay_carries_catalysts_and_evidence():
    from dashboard.live import overlay_snapshot
    payload = {"as_of": "x", "price_time": "x", "market_indicators": [], "lenses": [],
               "stocks": [{"ticker": "000660", "company": "SK하이닉스", "sector": "반도체",
                           "lens_ids": [], "metrics": {"valuation":50,"quality":50,"growth":50,"revision":50,"momentum":50},
                           "evidence": [], "gaps": []}]}
    snapshot = {"as_of": "x", "generated_at": "x", "macro": {}, "stocks": {"000660": {
        "price": 210000, "catalysts": [{"type":"supply_contract","direction":"recent","date":"2026-06-01","days":4,"label":"공급계약 (6/1)"}],
        "metrics": {"valuation":55,"quality":55,"growth":55,"revision":55,"momentum":55},
        "data_quality": {"missing": [], "proxy": [], "errors": [], "as_of": "x"}}}}
    overlay_snapshot(payload, snapshot)
    s = payload["stocks"][0]
    assert s["catalysts"][0]["label"] == "공급계약 (6/1)"
    assert any("공급계약" in e for e in s["evidence"])
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현** — `dashboard/live.py` `_overlay_stock`에 추가
  - `if snap.get("catalysts"): stock["catalysts"] = list(snap["catalysts"]); _append_evidence(stock, "catalyst: " + snap["catalysts"][0]["label"])`.

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/live.py tests/test_live.py
git commit -m "feat(catalyst): inject catalysts into candidate via overlay"
```

---

## Task 5: render — 카드 catalyst 표기

**Files:** Modify `dashboard/render.py`, `tests/test_dashboard_render.py`

후보 카드(md+html)에 catalyst 표기: upcoming은 `다가오는: {label}`, recent는 `최근: {label}`. 카드당 최대 2건(upcoming 1 + recent 1).

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_dashboard_render.py`

```python
def test_render_shows_catalyst(catalyst_dashboard):
    from dashboard.render import render_dashboard_markdown, render_dashboard_html
    md = render_dashboard_markdown(catalyst_dashboard)
    html = render_dashboard_html(catalyst_dashboard)
    assert "공급계약" in md or "실적 D-" in md
    assert "공급계약" in html or "실적 D-" in html
```

> `catalyst_dashboard`는 기존 render 테스트 Dashboard 헬퍼에 candidate 하나의 `catalysts`만 채워 새로 작성(없는 헬퍼 import 금지).

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현** — `dashboard/render.py`
  - markdown 후보 줄 하위에 catalyst가 있으면 `  - catalyst: 다가오는 {label} · 최근 {label}` 추가.
  - html 후보 카드에 catalyst 스팬/줄 추가(기존 스타일 재사용).

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/render.py tests/test_dashboard_render.py
git commit -m "feat(catalyst): render upcoming/recent catalyst on candidate cards"
```

---

## Task 6: 라이브 스모크

- [ ] **Step 1: 스냅샷 스모크** (DART_API_KEY 있으면 KR 공급계약, yfinance US 실적일)

Run: `set -a; source .env; set +a; uv run python scripts/build_dashboard_snapshot.py`
Expected: 에러 없이 빌드. 일부 KR 종목에 `공급계약`, 일부 US 종목에 `실적 D-n` catalyst. 키/네트워크 실패는 빈 catalyst로 degrade(중단 없음).

- [ ] **Step 2: 렌더 확인** → `uv run python scripts/render_lens_dashboard.py` → 카드에 catalyst 표기.

- [ ] **Step 3: 전체 회귀** → `uv run pytest -q` 그린.

---

## Self-Review 체크

- **Spec coverage:** KR 공급계약(DART list.json)✓ / US 실적일(yfinance)✓ / catalyst dict 계약✓ / 모델·snapshot·live·render 배선✓ / graceful degrade(키/네트워크)✓ / KR forward 실적일 v1.1 명시✓.
- **Isolation/additive:** 모델 필드 기본값 추가, snapshot/live/render 추가만. bot.py/insight_lookup 미접촉.
- **Type consistency:** `fetch_catalysts`/`_supply_contract_catalysts`/`_days_until` 시그니처 일치. catalyst dict 키(type/direction/date/days/label/detail)가 snapshot→live→render 일관. `_find_corp_code` 재사용(기존 private, 같은 패키지).
- **Placeholder scan:** Task1 구현 블록의 `bgn` 오타 잔재는 주에 정정 명시. 테스트 픽스처는 기존 패턴 신규작성 명시.

## Cross-model review 예정
(b) Codex plan 리뷰 → 차이 머지 → Codex 구현 → (a) Opus code 리뷰.

## Cross-model review 반영 v2 (2026-06-06, Codex leg) — **본 섹션이 위 태스크 본문에 우선**

Codex 리뷰: CONDITIONAL, blocker 0, should-fix 3 + nit 3. 반영:

- **E-01 (sf, DART pagination):** `page_count=100` 1페이지만 fetch. 단일 기업 90일 공급계약은 100건 초과가 드물어 루프 없이 **최신 100건으로 cap**하되, 응답 `total_count`/`total_page`가 1 초과면 `data_gap`/log로 "공급계약 100건 초과 — 최신만" 표기(no-silent-cap). 루프는 v1.1.
- **E-02 (sf, rcept_dt 검증):** `_supply_contract_catalysts`에서 길이 체크만으로 부족 — 비정상 날짜(`20261340`)가 `date.fromisoformat` 예외 → **행 단위 try/except로 불량 행만 skip**(전체 KR fetch가 degrade되지 않게). `re.fullmatch(r"\d{8}", raw)` + per-row 예외 처리. 불량 날짜 행 skip 테스트 추가.
- **E-03 (sf, corp_code 공개화):** `data/fundamental.py`의 `_find_corp_code` → **public `find_corp_code`로 승격**(또는 wrapper 추가)하고 catalyst.py·fundamental.py 양쪽이 공용 import. private cross-module import 제거. `_load_corp_code_xml` 캐시 쓰기는 의도된 동작이므로 유지.
- **E-04 (nit, yfinance 버전):** lock은 yfinance **1.4.1**(2.x 아님). `_extract_earnings_date` 주석을 "yfinance 1.x: `.calendar`는 dict, 'Earnings Date'는 date/Timestamp 리스트"로 교정. dict 형태 unit test 추가(monkeypatch로 fake `yf.Ticker.calendar`).
- **E-05 (nit, bgn 오타):** 구현 시 `bgn = replace(day=1)` 잔재 줄 삭제, `bgn = _minus_days(today, 90)`만.
- **E-06 (nit, CONTEXT 정합):** CONTEXT.md catalyst 용어가 "실적발표일(KR/US)"로 양쪽 v1 포함을 시사 → **v1은 US 실적일 + KR 공급계약, KR 실적일은 v1.1**로 CONTEXT 갱신(본 plan과 함께 커밋).

## 다음 Plan
Plan 6 밸류에이션 기대치(forward-pe 흡수) / Plan 7 정책 렌즈(저PBR). v1.1: KR 다가오는 실적일(네이버), DART 공급계약 pagination, 락업·지수편입.
