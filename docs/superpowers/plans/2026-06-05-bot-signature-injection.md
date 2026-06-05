# Bot Signature Injection — 독립성·수급·공매도 → 후보 카드 (Plan 5 / lens-dashboard 고도화)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans. 체크박스로 추적.
>
> **모든 명령:** `cd /Users/kjun/vault/01_Projects/04_stock_intel` 후 `uv run ...`.

**Goal:** 이 봇만의 차별점인 **감사인 독립성 차단·수급·공매도**를 상황판 후보 카드의 `risk_flags`로 주입한다. 독립성 BLOCKED(삼정 보유 등) 후보는 universe에서 **침묵 제외하지 않고** 🚫 차단 배지 + 랭킹 강등으로 보이게 유지한다. 방금 들어온 국장 후보(Plan 4)에 바로 독립성 판정이 붙는다.

**Architecture:** 기존 자산 재사용 — `signals/independence.decide_independence`, `data/audit_firm.fetch_audit_firm`, RawStock의 `net_flow_signal`/`short_ratio`. 새 overlay helper가 KR 후보별로 audit→독립성 판정을 계산(kreports 미가용 시 graceful degrade). snapshot이 독립성·수급·공매도를 stock dict로 carry, live가 후보에 주입(blocked flag + risk_flags + evidence), screeners가 BLOCKED를 랭킹 강등(제외 아님), render가 🚫 배지.

**Tech Stack:** Python 3.12, 기존 `dashboard/`·`signals/`·`data/` 패키지, pytest. kreports DB는 선택 의존(미가용 시 `🟡 독립성 확인 필요`로 degrade). 추가 외부 의존 없음.

**근거:** [CONTEXT.md](../../../CONTEXT.md) `봇 시그니처 주입 (Signature Injection)`·`라벨 네임스페이스 분리`(독립성 4: BLOCKED/CLEAR/MANUAL_VERIFY/UNKNOWN_MARKET), Plan 4(국장 후보 universe, 머지됨).

---

## Scope

### 포함
- `dashboard/providers/independence_overlay.py` 신규 — `fetch_independence(ticker)` (audit→decide_independence, graceful degrade) + 순수 `independence_flag(status)` 매핑.
- `dashboard/models.py` — `StockInput`/`Candidate`에 `independence_status`/`auditor` 필드(추가만; `blocked` 이미 존재).
- `dashboard/snapshot.py` — KR 후보별 독립성 overlay(injectable) + `net_flow_signal`/`short_ratio` carry.
- `dashboard/live.py` — 독립성/수급/공매도를 stock에 주입(blocked flag, evidence, gaps).
- `dashboard/screeners.py` — `_risk_flags`에 독립성·수급·공매도 추가 + `build_dashboard` 정렬에 BLOCKED 강등.
- `dashboard/render.py` — 후보 카드 🚫/🟡 독립성 배지(md+html).
- 테스트.

### 비범위
- 미국/일본 감사인 자동 조회(decide_independence가 MANUAL_VERIFY 반환 → 🟡) — v1.1.
- catalyst(Plan 3) / 밸류에이션 기대치(Plan 6) / 정책 렌즈(Plan 7).
- kreports DB 자동 수집 파이프라인 변경(기존 `_try_collect_auditors` 그대로).

---

## 독립성 status → 라벨/차단 매핑 (확정)

| decide_independence status | risk_flag | blocked |
|---|---|---|
| `BLOCKED_CONFIRMED` | `🚫 독립성 차단 — 매입 검토 금지` | True |
| `BLOCKED_POSSIBLE` | `🚫 독립성 차단 가능 — 원천 확인 전 보류` | True |
| `MANUAL_VERIFY` / `MANUAL_VERIFY_CURRENT_YEAR` / `ROLLOVER_INFERRED` / `DATA_MISSING` / `UNKNOWN_MARKET` | `🟡 독립성 확인 필요` | False |
| `CLEAR_CONFIRMED` | (flag 없음) | False |

수급: `net_flow_signal < 0` → `수급 순매도`. 공매도: `short_ratio >= 5.0` → `공매도 비중 높음(약 {x}%)`.

---

## File Structure

| 파일 | 책임 | 신규/수정 |
|---|---|---|
| `dashboard/providers/independence_overlay.py` | audit→독립성 판정 fetch + flag 매핑(순수) | 신규 |
| `dashboard/models.py` | StockInput/Candidate independence 필드 | 수정(추가) |
| `dashboard/snapshot.py` | 독립성 overlay + 수급/공매도 carry | 수정 |
| `dashboard/live.py` | 후보 주입(blocked/evidence/gaps) | 수정 |
| `dashboard/screeners.py` | risk_flags + BLOCKED 강등 | 수정 |
| `dashboard/render.py` | 🚫/🟡 배지 | 수정 |
| tests/test_independence_overlay.py 외 | | 신규/수정 |

---

## 핵심 계약 (시그니처 고정)

```python
# dashboard/providers/independence_overlay.py
def independence_flag(status: str) -> tuple[str | None, bool]:
    # status -> (risk_flag 문자열 or None, blocked: bool). 위 매핑 표 그대로.
def fetch_independence(ticker: str, *, as_of_year: int | None = None) -> dict:
    # KR 6자리만 실제 판정; 그 외 MANUAL_VERIFY. kreports 미가용 시 DATA_MISSING.
    # returns {"status": str, "auditor": str | None, "reason": str}
```

---

## Task 1: independence overlay helper

**Files:** Create `dashboard/providers/independence_overlay.py`, `tests/test_independence_overlay.py`

- [ ] **Step 1: 실패 테스트** — `tests/test_independence_overlay.py`

```python
from dashboard.providers.independence_overlay import fetch_independence, independence_flag


def test_flag_mapping_blocked():
    flag, blocked = independence_flag("BLOCKED_CONFIRMED")
    assert blocked is True
    assert "독립성 차단" in flag


def test_flag_mapping_manual_verify():
    flag, blocked = independence_flag("MANUAL_VERIFY")
    assert blocked is False
    assert "독립성 확인 필요" in flag


def test_flag_mapping_clear_has_no_flag():
    flag, blocked = independence_flag("CLEAR_CONFIRMED")
    assert flag is None
    assert blocked is False


def test_fetch_independence_kr_blocked(monkeypatch):
    import dashboard.providers.independence_overlay as mod
    monkeypatch.setattr(mod, "fetch_audit_firm",
                        lambda t: {"current_year": 2026, "current_firm": "삼정회계법인",
                                   "recent": [{"year": 2026, "firm": "삼정회계법인"}]})
    out = fetch_independence("000660", as_of_year=2026)
    assert out["status"] == "BLOCKED_CONFIRMED"
    assert out["auditor"] == "삼정회계법인"


def test_fetch_independence_us_is_manual_verify():
    out = fetch_independence("NVDA")
    assert out["status"] == "MANUAL_VERIFY"


def test_fetch_independence_degrades_when_kreports_missing(monkeypatch):
    import dashboard.providers.independence_overlay as mod
    monkeypatch.setattr(mod, "fetch_audit_firm",
                        lambda t: {"error": "kreports DB에 접근할 수 없습니다."})
    out = fetch_independence("000660", as_of_year=2026)
    assert out["status"] == "DATA_MISSING"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_independence_overlay.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `dashboard/providers/independence_overlay.py`

```python
"""Audit-independence overlay for dashboard candidates (Plan 5).

기존 자산 재사용: data.audit_firm.fetch_audit_firm + signals.independence.
KR 6자리만 실제 판정. kreports 미가용/미국·일본은 graceful degrade.
"""

from __future__ import annotations

from data.audit_firm import fetch_audit_firm
from dashboard.providers.base import classify_market
from signals.independence import decide_independence
from signals.market import Market

_BLOCKED = {"BLOCKED_CONFIRMED", "BLOCKED_POSSIBLE"}
_MANUAL = {"MANUAL_VERIFY", "MANUAL_VERIFY_CURRENT_YEAR", "ROLLOVER_INFERRED",
           "DATA_MISSING", "UNKNOWN_MARKET"}

_BLOCKED_LABEL = {
    "BLOCKED_CONFIRMED": "🚫 독립성 차단 — 매입 검토 금지",
    "BLOCKED_POSSIBLE": "🚫 독립성 차단 가능 — 원천 확인 전 보류",
}


def independence_flag(status: str) -> tuple[str | None, bool]:
    if status in _BLOCKED:
        return _BLOCKED_LABEL[status], True
    if status in _MANUAL:
        return "🟡 독립성 확인 필요", False
    return None, False  # CLEAR_CONFIRMED


def fetch_independence(ticker: str, *, as_of_year: int | None = None) -> dict:
    market = classify_market(ticker)
    if market != "KR":
        decision = decide_independence(Market(market, market), {}, as_of_year=as_of_year)
        return {"status": decision.status, "auditor": decision.auditor, "reason": decision.reason}
    try:
        audit = fetch_audit_firm(ticker)
    except Exception as exc:  # pragma: no cover - defensive
        return {"status": "DATA_MISSING", "auditor": None, "reason": f"감사인 조회 실패: {type(exc).__name__}"}
    decision = decide_independence(Market("KR", "한국"), audit, as_of_year=as_of_year)
    return {"status": decision.status, "auditor": decision.auditor, "reason": decision.reason}
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_independence_overlay.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/providers/independence_overlay.py tests/test_independence_overlay.py
git commit -m "feat(signature): audit-independence overlay helper (reuse decide_independence)"
```

---

## Task 2: 모델 — StockInput/Candidate independence 필드

**Files:** Modify `dashboard/models.py`, `tests/test_dashboard_models.py`

`StockInput`에 `independence_status: str = ""`, `auditor: str = ""` 추가(`blocked` 기존). `Candidate`에 동일 2필드 추가. `parse_dashboard_input`이 `item.get("independence_status","")`/`item.get("auditor","")` 파싱.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_dashboard_models.py`

```python
def test_parse_stock_carries_independence():
    from dashboard.models import parse_dashboard_input
    payload = _minimal_payload_with_one_stock(independence_status="BLOCKED_CONFIRMED", auditor="삼정회계법인")
    parsed = parse_dashboard_input(payload)
    s = parsed.stocks[0]
    assert s.independence_status == "BLOCKED_CONFIRMED"
    assert s.auditor == "삼정회계법인"
```

> `_minimal_payload_with_one_stock`은 기존 test_dashboard_models.py의 페이로드 헬퍼/패턴을 재사용해 stock 하나에 `independence_status`/`auditor`만 추가하라(새 픽스처 발명 금지).

- [ ] **Step 2: 실패 확인** → FAIL (AttributeError independence_status)

- [ ] **Step 3: 구현** — `dashboard/models.py`
  - `@dataclass StockInput`: `independence_status: str = ""`, `auditor: str = ""` 추가(기본값, 기존 호환).
  - `@dataclass Candidate`: 동일 2필드 추가(마지막).
  - `parse_dashboard_input`의 StockInput 생성에 `independence_status=str(item.get("independence_status",""))`, `auditor=str(item.get("auditor",""))`.

- [ ] **Step 4: 통과 + 전체 회귀** → `uv run pytest -q` 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/models.py tests/test_dashboard_models.py
git commit -m "feat(signature): independence_status/auditor on StockInput/Candidate"
```

---

## Task 3: snapshot — 독립성 overlay + 수급/공매도 carry

**Files:** Modify `dashboard/snapshot.py`, `tests/test_snapshot.py`

`build_snapshot`에 injectable `independence: Callable[[str], dict] = fetch_independence` 추가. 각 ticker stock dict에 `independence_status`/`auditor`/`independence_reason`, 그리고 `net_flow_signal`(raw에서) 추가(`short_ratio` 이미 carry). 단위테스트는 fake independence 주입.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_snapshot.py`

```python
def test_snapshot_carries_independence_and_flow():
    from dashboard.snapshot import build_snapshot, UniverseEntry
    from dashboard.providers.base import RawStock
    raw = RawStock("000660", "KR", price=210000, pe=8, net_flow_signal=-1.0, short_ratio=6.2)
    snap = build_snapshot(
        [UniverseEntry("000660", "반도체")],
        fetch=lambda t: raw,
        macro=lambda: {"market_indicators": [], "errors": []},
        independence=lambda t: {"status": "BLOCKED_CONFIRMED", "auditor": "삼정회계법인", "reason": "차단"},
        as_of="2026-06-05",
    )
    s = snap["stocks"]["000660"]
    assert s["independence_status"] == "BLOCKED_CONFIRMED"
    assert s["auditor"] == "삼정회계법인"
    assert s["net_flow_signal"] == -1.0
    assert s["short_ratio"] == 6.2
```

- [ ] **Step 2: 실패 확인** → FAIL (KeyError independence_status)

- [ ] **Step 3: 구현** — `dashboard/snapshot.py`
  - import `from dashboard.providers.independence_overlay import fetch_independence`.
  - `build_snapshot(..., independence: Callable[[str], dict] = fetch_independence)`.
  - stock dict에 추가: `ind = independence(ticker)`(try/except로 degrade), `"independence_status": ind.get("status",""), "auditor": ind.get("auditor"), "independence_reason": ind.get("reason",""), "net_flow_signal": raw.net_flow_signal`.

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/snapshot.py tests/test_snapshot.py
git commit -m "feat(signature): snapshot carries independence + net flow + short ratio"
```

---

## Task 4: live overlay — 후보에 주입 (blocked/evidence/gaps)

**Files:** Modify `dashboard/live.py`, `tests/test_live.py`

`_overlay_stock`이 snapshot의 독립성/수급/공매도를 stock payload로:
- `independence_status`/`auditor` 복사.
- BLOCKED status면 `stock["blocked"] = True`.
- evidence에 독립성 reason(`🚫`/`🟡`/`🟢` 한 줄), 수급(순매도면), 공매도(비중 높으면) 추가.
- CLEAR면 `🟢 독립성 확인` evidence.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_live.py`

```python
def test_overlay_sets_blocked_and_independence_evidence():
    from dashboard.live import overlay_snapshot
    payload = {"as_of": "x", "price_time": "x", "market_indicators": [], "lenses": [],
               "stocks": [{"ticker": "000660", "company": "SK하이닉스", "sector": "반도체",
                           "lens_ids": [], "metrics": {"valuation":50,"quality":50,"growth":50,"revision":50,"momentum":50},
                           "evidence": [], "gaps": []}]}
    snapshot = {"as_of": "x", "generated_at": "x", "macro": {}, "stocks": {"000660": {
        "price": 210000, "independence_status": "BLOCKED_CONFIRMED", "auditor": "삼정회계법인",
        "independence_reason": "차단", "net_flow_signal": -1.0, "short_ratio": 6.2,
        "metrics": {"valuation":60,"quality":55,"growth":55,"revision":55,"momentum":55},
        "data_quality": {"missing": [], "proxy": [], "errors": [], "as_of": "x"}}}}
    overlay_snapshot(payload, snapshot)
    s = payload["stocks"][0]
    assert s["blocked"] is True
    assert s["independence_status"] == "BLOCKED_CONFIRMED"
    assert any("독립성 차단" in e for e in s["evidence"])
    assert any("순매도" in e for e in s["evidence"])
    assert any("공매도" in e for e in s["evidence"])
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현** — `dashboard/live.py` `_overlay_stock`에 추가
  - `from dashboard.providers.independence_overlay import independence_flag`.
  - `status = snap.get("independence_status")`; `flag, blocked = independence_flag(status)` (status 있을 때).
  - `if blocked: stock["blocked"] = True`.
  - `stock["independence_status"] = status`; `stock["auditor"] = snap.get("auditor") or ""`.
  - evidence: blocked/manual면 `_append_evidence(stock, flag + (f" · {auditor}" if auditor else ""))`; CLEAR면 `🟢 독립성 확인`.
  - 수급: `snap.get("net_flow_signal") < 0` → `_append_evidence(stock, "수급: 기관·외국인 순매도")`.
  - 공매도: `snap.get("short_ratio") >= 5.0` → `_append_evidence(stock, f"공매도 비중 높음 (약 {short:.1f}%)")`.

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/live.py tests/test_live.py
git commit -m "feat(signature): inject independence/flow/short into candidate via overlay"
```

---

## Task 5: screeners — risk_flags + BLOCKED 강등 (제외 아님)

**Files:** Modify `dashboard/screeners.py`, `tests/test_dashboard_screeners.py`

`_risk_flags(stock, score)`에 추가: 독립성 flag(`independence_flag(stock.independence_status)[0]`이 있으면), 수급/공매도는 evidence로 이미 들어가나 risk_flags에도 `수급 순매도`/`공매도 과다` 노출. `build_dashboard` 정렬 키에 **BLOCKED 강등**: BLOCKED 후보가 맨 아래로(제외 아님). 정렬 키 맨 앞에 `item.status == CandidateStatus.BLOCKED` 추가(False < True → 비차단 먼저, 차단 맨 뒤).

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_dashboard_screeners.py`

```python
def test_blocked_candidate_demoted_not_excluded():
    from dashboard.screeners import build_dashboard
    from dashboard.models import parse_dashboard_input
    payload = _two_stock_payload(  # 기존 헬퍼 재사용
        blocked={"ticker": "000660", "independence_status": "BLOCKED_CONFIRMED", "blocked": True},
        clean={"ticker": "035420", "independence_status": "CLEAR_CONFIRMED"},
    )
    dash = build_dashboard(parse_dashboard_input(payload))
    tickers = [c.ticker for c in dash.candidates]
    assert "000660" in tickers                 # 제외 안 됨
    assert tickers.index("000660") == len(tickers) - 1  # 맨 뒤로 강등
    blocked = next(c for c in dash.candidates if c.ticker == "000660")
    assert any("독립성 차단" in f for f in blocked.risk_flags)
```

> `_two_stock_payload`는 기존 test_dashboard_screeners.py 픽스처 패턴 재사용.

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현** — `dashboard/screeners.py`
  - import `from dashboard.providers.independence_overlay import independence_flag`.
  - `_risk_flags`: 시작에 `flag, _ = independence_flag(stock.independence_status); if flag: flags.append(flag)`. 수급/공매도는 stock에 carry된 값으로 추가(StockInput에 net_flow/short 없으면 evidence로만; 본 plan은 risk_flags에 독립성만 필수, 수급/공매도는 evidence 우선 — Task4에서 evidence 처리됨).
  - `build_dashboard` 정렬 key 맨 앞에 `item.status == CandidateStatus.BLOCKED` 추가.

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/screeners.py tests/test_dashboard_screeners.py
git commit -m "feat(signature): independence risk_flag + demote (not exclude) BLOCKED candidates"
```

---

## Task 6: render — 🚫/🟡 독립성 배지

**Files:** Modify `dashboard/render.py`, `tests/test_dashboard_render.py`

후보 카드(md+html)에 독립성 배지: BLOCKED → 🚫(경고색), MANUAL → 🟡, CLEAR → 🟢(또는 생략). 기존 candidate 렌더 위치에 배지 한 줄/스팬 추가.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_dashboard_render.py`

```python
def test_render_shows_blocked_badge(blocked_candidate_dashboard):
    from dashboard.render import render_dashboard_markdown, render_dashboard_html
    md = render_dashboard_markdown(blocked_candidate_dashboard)
    html = render_dashboard_html(blocked_candidate_dashboard)
    assert "🚫" in md and "독립성 차단" in md
    assert "🚫" in html
```

> `blocked_candidate_dashboard`는 기존 render 테스트 Dashboard 헬퍼에 candidate 하나를 `independence_status="BLOCKED_CONFIRMED"`, `risk_flags=["🚫 독립성 차단 — 매입 검토 금지"]`로 구성(기존 픽스처 재사용).

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현** — `dashboard/render.py`
  - markdown 후보 줄에 `independence_status`가 BLOCKED/MANUAL이면 배지 텍스트 추가(risk_flags의 독립성 flag 노출).
  - html 후보 카드에 `<span class="hbadge bbad">🚫 독립성 차단</span>`(BLOCKED) / `bneu`(MANUAL) 추가. 기존 배지 스타일 클래스 재사용.

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/render.py tests/test_dashboard_render.py
git commit -m "feat(signature): render independence badge on candidate cards"
```

---

## Task 7: 라이브 스모크

- [ ] **Step 1: 스냅샷 스모크** (kreports DB 있으면 실판정, 없으면 🟡 degrade)

Run: `set -a; source .env; set +a; uv run python scripts/build_dashboard_snapshot.py`
Expected: 에러 없이 빌드. KR 후보에 independence_status 채워짐(kreports 미가용이면 DATA_MISSING→🟡). 삼정 보유 KR 종목이 있으면 🚫 BLOCKED + 랭킹 하단.

- [ ] **Step 2: 렌더 확인**

Run: `uv run python scripts/render_lens_dashboard.py`
Expected: 후보 카드에 🚫/🟡 배지, BLOCKED 종목이 상위 후보 하단에 위치(제외 안 됨).

- [ ] **Step 3: 전체 회귀** → `uv run pytest -q` 그린.

---

## Self-Review 체크

- **Spec coverage:** 독립성 판정 재사용(decide_independence)✓ / BLOCKED 🚫+강등(제외 아님)✓ / 수급·공매도 evidence✓ / risk_flags 독립성✓ / kreports 미가용 graceful degrade(🟡)✓ / 라벨 네임스페이스 분리(독립성 4-state)✓ / US·JP MANUAL_VERIFY✓.
- **Isolation/additive:** 모델 필드 기본값 추가, snapshot/live/screeners/render 추가만. bot.py·insight_lookup 등 별도작업 미접촉.
- **Type consistency:** `fetch_independence`/`independence_flag` 시그니처 일치. status 값이 signals.independence와 정확히 동일 문자열. snapshot→live→screeners→render에서 `independence_status`/`auditor`/`net_flow_signal`/`short_ratio` 키 일관.
- **Placeholder scan:** 테스트 픽스처는 기존 재사용 명시(발명 금지).

## Cross-model review 예정
(b) Codex plan 리뷰 → 차이 머지 → Codex 구현 → (a) Opus code 리뷰.

## Cross-model review 반영 v2 (2026-06-05, Codex leg) — **본 섹션이 위 태스크 본문에 우선**

Codex 리뷰: blocker 0, should-fix 2. Point 1·3·4·5·6 PASS(검증됨). 반영:

- **D-01 (Point 2 — 비-KR market 분류):** `classify_market`는 **KR/US만** 반환(JP/UNKNOWN 분기 없음). 따라서 dashboard v1에서 **비-KR 티커는 전부 US로 분류 → `decide_independence`가 `MANUAL_VERIFY` → 🟡 독립성 확인 필요**로 degrade(기능상 정상: 미국·일본·기타 모두 자동 확인 미지원이라 🟡이 맞음). `fetch_independence`의 비-KR 분기는 `Market("US", "미국")`(생성자 `(code, label)`)로 호출하면 됨 — 별도 JP 분기 불필요. test_fetch_independence_us_is_manual_verify 그대로 유효. (JP 자동조회는 v1.1; classify_market 확장은 비범위.)
- **D-02 (Point 7 — 테스트 픽스처·CSS):**
  - `_minimal_payload_with_one_stock`/`_two_stock_payload`/`blocked_candidate_dashboard`는 **기존 파일에 없다**(plan 발명). 구현자는 **각 테스트 파일의 기존 인라인 페이로드/대시보드 생성 패턴을 그대로 따라 새로 작성**한다(이미 있는 헬퍼인 척 import 금지). 예: test_dashboard_screeners.py의 기존 stock dict 구성 방식을 복제해 2종목(blocked/clean) 페이로드를 인라인으로 만든다.
  - render: `.hbadge.bneu`만 존재하고 **`.hbadge.bbad`는 없다**. Task 6에서 BLOCKED 배지용 `.hbadge.bbad`(경고/적색) CSS 클래스를 **추가**하고, MANUAL은 기존 `.bneu` 재사용. md는 🚫/🟡 텍스트.

## 다음 Plan
Plan 3 catalyst / Plan 6 밸류에이션 기대치(forward-pe) / Plan 7 정책 렌즈(저PBR).
