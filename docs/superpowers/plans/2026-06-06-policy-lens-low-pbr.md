# Policy Lens — 저PBR 밸류업 (Plan 7 / lens-dashboard 고도화)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans. 체크박스로 추적.
>
> **모든 명령:** `cd /Users/kjun/vault/01_Projects/04_stock_intel` 후 `uv run ...`.

**Goal:** 정부·규제 정책이 드라이버인 수혜주를 추적하는 **정책 렌즈(`LensKind.POLICY`)** 를 신설하고, 첫 인스턴스로 **저PBR 밸류업**을 붙인다. 멤버십 = **큐레이션 시드 10종목 + PBR<임계 자동 스크린**(하이브리드). 향후 IRA·CHIPS·K-방산도 같은 칸에 슬롯인.

**Architecture:** `LensKind.POLICY` enum + `dashboard/policy_lens.py`(저PBR 밸류업 Lens 정의 + 시드 10종목 → stock 변환, Plan 4 kr_universe 패턴). market_insights가 lens·시드를 universe에 union. **PBR 스크린 augment는 live overlay**에서 — 스냅샷 pbr < 임계면 `value_up_low_pbr` lens를 동적 추가(하이브리드). 렌더는 기존 lens 히트맵 재사용.

**Tech Stack:** Python 3.12, 기존 `dashboard/` 패키지, pytest. 추가 외부 의존 없음(PBR은 기존 snapshot raw.pbr 재사용).

**근거:** [CONTEXT.md](../../../CONTEXT.md) `정책 렌즈 (Policy Lens)`·`저PBR 밸류업 렌즈`, Plan 1~6(머지됨).

**시드 10종목(2026-06-06 ticker cache 확정):** 현대제철 004020 · 롯데케미칼 011170 · 금호석유화학 011780 · OCI홀딩스 010060 · 동국제강 460860 · 세아베스틸지주 001430 · GS 078930 · SK 034730 · 한화 000880 · 태광산업 003240.

---

## Scope

### 포함
- `dashboard/models.py` — `LensKind.POLICY = "policy"` enum 추가.
- `dashboard/policy_lens.py` 신규 — `VALUE_UP_LENS`(Lens dict) + `LOW_PBR_SEEDS`(10종목) + `low_pbr_seed_stocks()` + `policy_lenses()`.
- `dashboard/market_insights.py` — `payload["lenses"]`에 정책 렌즈 추가 + 시드 stocks union-merge(`_merge_kr_screen` 재사용/동형).
- `dashboard/live.py` — PBR 스크린 augment(스냅샷 pbr<임계면 lens_ids에 `value_up_low_pbr` 추가).
- 테스트.

### 비범위 (v1.1)
- 다른 정책(IRA·CHIPS·K-방산) 인스턴스 — 프레임만 만들고 인스턴스는 후속.
- 자사주 소각·배당 정책 공시 catalyst 연동(Plan 3 catalyst 확장) — 후속.
- 정책 렌즈 전용 점수 가중(매력도는 기존 lens weights 사용).

---

## 정책 렌즈 정의 (확정)

```python
VALUE_UP_LENS = {
    "id": "value_up_low_pbr",
    "kind": "policy",
    "name": "저PBR 밸류업",
    "conviction": "medium",
    "direction": "long",
    "weights": {"valuation": 0.6, "quality": 0.2, "growth": 0.0, "revision": 0.1, "momentum": 0.1},
    "risks": ["밸류업 정책 동력 약화 시 저PBR 재평가 지연", "업황 회복 지연 시 자산가치 할인 지속"],
}
```
thesis: "정부 밸류업 프로그램이 저PBR 자산주 재평가를 유도". PBR 스크린 임계: **PBR < 0.5**(deep value; 상수 `LOW_PBR_THRESHOLD`, tunable).

---

## File Structure

| 파일 | 책임 | 신규/수정 |
|---|---|---|
| `dashboard/models.py` | LensKind.POLICY | 수정(추가) |
| `dashboard/policy_lens.py` | 정책 렌즈 def + 저PBR 시드 + 변환 | 신규 |
| `dashboard/market_insights.py` | 렌즈·시드 union | 수정 |
| `dashboard/live.py` | PBR 스크린 augment | 수정 |
| tests/test_policy_lens.py 외 | | 신규/수정 |

---

## 핵심 계약 (시그니처 고정)

```python
# dashboard/policy_lens.py
VALUE_UP_LENS: dict
LOW_PBR_SEEDS: tuple   # (code, name, pbr_band, feature)
LOW_PBR_THRESHOLD = 0.5
def policy_lenses() -> list[dict]            # [VALUE_UP_LENS]
def low_pbr_seed_stocks() -> list[dict]      # 10종목 stock payload
def seed_to_stock(seed) -> dict
```

---

## Task 1: LensKind.POLICY

**Files:** Modify `dashboard/models.py`, `tests/test_dashboard_models.py`

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_dashboard_models.py`

```python
def test_lens_kind_policy_parses():
    from dashboard.models import LensKind, parse_dashboard_input
    payload = _payload_with_policy_lens()  # 기존 인라인 패턴 신규작성: lens kind "policy" 1개
    parsed = parse_dashboard_input(payload)
    assert any(l.kind == LensKind.POLICY for l in parsed.lenses)
```

- [ ] **Step 2~5:** `LensKind`에 `POLICY = "policy"` 추가 → 통과 → 회귀 → 커밋.

```bash
git commit -m "feat(policy-lens): add LensKind.POLICY"
```

---

## Task 2: 정책 렌즈 정의 + 저PBR 시드

**Files:** Create `dashboard/policy_lens.py`, `tests/test_policy_lens.py`

- [ ] **Step 1: 실패 테스트** — `tests/test_policy_lens.py`

```python
from dashboard.policy_lens import (
    LOW_PBR_SEEDS,
    VALUE_UP_LENS,
    low_pbr_seed_stocks,
    policy_lenses,
)


def test_value_up_lens_is_policy_kind():
    assert VALUE_UP_LENS["kind"] == "policy"
    assert VALUE_UP_LENS["id"] == "value_up_low_pbr"
    assert VALUE_UP_LENS["weights"]["valuation"] >= 0.5  # 저PBR이므로 valuation 가중


def test_seeds_cover_ten_with_codes():
    codes = {c for c, *_ in LOW_PBR_SEEDS}
    assert {"004020", "011170", "011780", "010060", "460860",
            "001430", "078930", "034730", "000880", "003240"} <= codes


def test_low_pbr_seed_stocks_shape():
    stocks = low_pbr_seed_stocks()
    assert len(stocks) == 10
    s = next(x for x in stocks if x["ticker"] == "004020")
    assert s["company"] == "현대제철"
    assert "value_up_low_pbr" in s["lens_ids"]
    assert "밸류업" in s["thesis"]
    assert all(k in s for k in ("metrics", "evidence", "gaps", "next_action", "source_refs", "peer_group"))


def test_policy_lenses_returns_value_up():
    assert policy_lenses()[0]["id"] == "value_up_low_pbr"
```

- [ ] **Step 2: 실패 확인** → FAIL (ModuleNotFoundError)

- [ ] **Step 3: 구현** — `dashboard/policy_lens.py`

```python
"""Policy lens (LensKind.POLICY) — 저PBR 밸류업 첫 인스턴스 (Plan 7).

멤버십 하이브리드: 큐레이션 시드 10종목(아래) + PBR<임계 자동 스크린(live overlay).
실데이터(가격/PBR/지표)는 기존 snapshot overlay가 ticker로 붙인다.
"""

from __future__ import annotations

LOW_PBR_THRESHOLD = 0.5

VALUE_UP_LENS = {
    "id": "value_up_low_pbr",
    "kind": "policy",
    "name": "저PBR 밸류업",
    "conviction": "medium",
    "direction": "long",
    "weights": {"valuation": 0.6, "quality": 0.2, "growth": 0.0, "revision": 0.1, "momentum": 0.1},
    "risks": ["밸류업 정책 동력 약화 시 저PBR 재평가 지연", "업황 회복 지연 시 자산가치 할인 지속"],
}

# (code, name, pbr_band, feature) — 2026-06-06 ticker cache 확정.
LOW_PBR_SEEDS = (
    ("004020", "현대제철", "0.2배대", "철강 업황 회복 + 미국 투자 옵션"),
    ("011170", "롯데케미칼", "0.2배대", "석유화학 최악 업황 반영"),
    ("011780", "금호석유화학", "0.3배 전후", "고배당 + 화학 업황 회복 수혜"),
    ("010060", "OCI홀딩스", "0.3배 전후", "태양광 사이클 회복 기대"),
    ("460860", "동국제강", "0.2~0.3배", "철강 업황 레버리지"),
    ("001430", "세아베스틸지주", "0.2배대", "특수강 사이클"),
    ("078930", "GS", "0.3배대", "정유·발전 자산 보유"),
    ("034730", "SK", "0.3배대", "NAV 할인 극심"),
    ("000880", "한화", "0.3배대", "방산·태양광 가치 대비 할인"),
    ("003240", "태광산업", "0.2배대", "현금성 자산 많음"),
)

_NEUTRAL_METRICS = {"valuation": 50, "quality": 50, "growth": 50, "revision": 50, "momentum": 50}


def policy_lenses() -> list[dict]:
    return [dict(VALUE_UP_LENS)]


def seed_to_stock(seed) -> dict:
    code, name, pbr_band, feature = seed
    return {
        "ticker": code,
        "company": name,
        "sector": "저PBR 밸류업",
        "lens_ids": ["value_up_low_pbr"],
        "thesis": f"{name}: 정부 밸류업 프로그램이 저PBR 자산주({pbr_band}) 재평가를 유도하는지 보는 정책 카드 — {feature}.",
        "metrics": dict(_NEUTRAL_METRICS),
        "evidence": [f"저PBR 밸류업 시드: 대략 PBR {pbr_band}", feature],
        "bull_case": [f"밸류업(자사주·배당) 강화 시 {pbr_band} 저PBR 재평가 여지 — {feature}"],
        "bear_case": ["정책 동력/업황 회복이 늦으면 자산가치 할인이 지속될 수 있음."],
        "gaps": [
            "저PBR 밸류업 시드 — 실데이터(PBR·가격·자사주/배당 공시) 스냅샷 overlay 필요",
            "PBR 임계 자동 스크린은 live overlay에서 보강",
        ],
        "next_action": "최근 PBR·자사주 소각/배당 정책 공시와 업황 회복 신호를 확인해 재평가 여부 판단.",
        "source_refs": ["저PBR 밸류업 정책 렌즈"],
        "peer_group": "저PBR 밸류업",
    }


def low_pbr_seed_stocks() -> list[dict]:
    return [seed_to_stock(s) for s in LOW_PBR_SEEDS]
```

- [ ] **Step 4: 통과 + 커밋**

```bash
git add dashboard/policy_lens.py tests/test_policy_lens.py
git commit -m "feat(policy-lens): 저PBR 밸류업 lens def + 10 curated seeds"
```

---

## Task 3: market_insights union (lens + 시드)

**Files:** Modify `dashboard/market_insights.py`, `tests/test_market_insights.py`

`build_market_insights_payload`가 (a) `payload["lenses"]`에 `policy_lenses()` 추가(중복 id 방지), (b) 시드 stocks를 `_merge_kr_screen` 동형으로 union. 기존 큐레이션/KR 스크린 보존.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_market_insights.py`

```python
def test_payload_includes_policy_lens_and_low_pbr_seeds(tmp_path):
    payload = build_market_insights_payload(insights_dir=tmp_path)
    lens_ids = {l["id"] for l in payload["lenses"]}
    assert "value_up_low_pbr" in lens_ids
    tickers = {str(s["ticker"]) for s in payload["stocks"]}
    assert "004020" in tickers and "034730" in tickers   # 현대제철·SK
    sk = next(s for s in payload["stocks"] if str(s["ticker"]) == "034730")
    assert "value_up_low_pbr" in sk["lens_ids"]
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현** — `dashboard/market_insights.py`
  - import `from dashboard.policy_lens import policy_lenses, low_pbr_seed_stocks`.
  - `build_market_insights_payload`에서 lenses union(id 기준 dedup) + `payload["stocks"] = _merge_kr_screen(payload["stocks"], low_pbr_seed_stocks())`.
  - (이미 KR 스크린 시드와 동일 종목이 있으면 `_merge_kr_screen` dedup이 source_refs/lens 합집합 처리.)

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/market_insights.py tests/test_market_insights.py
git commit -m "feat(policy-lens): union 저PBR seeds + policy lens into universe"
```

---

## Task 4: PBR 스크린 augment (live overlay)

**Files:** Modify `dashboard/live.py`, `tests/test_live.py`

`_overlay_stock`에서 스냅샷 `pbr`가 `LOW_PBR_THRESHOLD` 미만이면 stock `lens_ids`에 `value_up_low_pbr`를 동적 추가(이미 있으면 skip) + evidence 한 줄. → 큐레이션(시드) + 스크린(자동) 하이브리드 멤버십.

스냅샷에 `pbr`가 carry되는지 확인(snapshot.py는 `pbr` carry함). 없으면 carry 추가.

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_live.py`

```python
def test_low_pbr_stock_auto_joins_policy_lens():
    from dashboard.live import overlay_snapshot
    payload = {"as_of": "x", "price_time": "x", "market_indicators": [], "lenses": [],
               "stocks": [{"ticker": "005490", "company": "POSCO", "sector": "철강",
                           "lens_ids": [], "metrics": {"valuation":50,"quality":50,"growth":50,"revision":50,"momentum":50},
                           "evidence": [], "gaps": []}]}
    snapshot = {"as_of": "x", "generated_at": "x", "macro": {}, "stocks": {"005490": {
        "price": 300000, "pbr": 0.42,
        "metrics": {"valuation":70,"quality":55,"growth":50,"revision":50,"momentum":50},
        "data_quality": {"missing": [], "proxy": [], "errors": [], "as_of": "x"}}}}
    overlay_snapshot(payload, snapshot)
    s = payload["stocks"][0]
    assert "value_up_low_pbr" in s["lens_ids"]      # PBR 0.42 < 0.5 → 자동 편입
    assert any("저PBR" in e for e in s["evidence"])


def test_high_pbr_stock_not_joined():
    from dashboard.live import overlay_snapshot
    payload = {"as_of": "x", "price_time": "x", "market_indicators": [], "lenses": [],
               "stocks": [{"ticker": "005930", "company": "삼성전자", "sector": "반도체",
                           "lens_ids": [], "metrics": {"valuation":50,"quality":50,"growth":50,"revision":50,"momentum":50},
                           "evidence": [], "gaps": []}]}
    snapshot = {"as_of": "x", "generated_at": "x", "macro": {}, "stocks": {"005930": {
        "price": 80000, "pbr": 1.4,
        "metrics": {"valuation":50,"quality":50,"growth":50,"revision":50,"momentum":50},
        "data_quality": {"missing": [], "proxy": [], "errors": [], "as_of": "x"}}}}
    overlay_snapshot(payload, snapshot)
    assert "value_up_low_pbr" not in payload["stocks"][0]["lens_ids"]
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**
  - `snapshot.py`: stock dict에 `pbr` carry 확인/추가(`_round(raw.pbr, 2)`; 이미 있으면 유지).
  - `live.py _overlay_stock`: `from dashboard.policy_lens import LOW_PBR_THRESHOLD`. `pbr = snap.get("pbr"); if pbr is not None and pbr < LOW_PBR_THRESHOLD and "value_up_low_pbr" not in stock.get("lens_ids", []): stock["lens_ids"] = [*stock.get("lens_ids", []), "value_up_low_pbr"]; _append_evidence(stock, f"저PBR 밸류업 자동 편입 (PBR {pbr:.2f} < {LOW_PBR_THRESHOLD})")`.

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/live.py dashboard/snapshot.py tests/test_live.py
git commit -m "feat(policy-lens): auto-join low-PBR stocks to 저PBR 밸류업 lens (hybrid screen)"
```

---

## Task 5: 라이브 스모크 + 렌더 확인

- [ ] **Step 1: universe/lens 확인(네트워크 없이)**

Run:
```bash
uv run python -c "from dashboard.market_insights import build_market_insights_payload as b; p=b(); print('정책렌즈:', any(l['id']=='value_up_low_pbr' for l in p['lenses'])); print('저PBR 시드 universe:', sum(1 for s in p['stocks'] if 'value_up_low_pbr' in s['lens_ids']))"
```
Expected: 정책렌즈 True, 저PBR 시드 ≥ 10.

- [ ] **Step 2: 라이브 스냅샷 스모크** — `set -a; source .env; set +a; uv run python scripts/build_dashboard_snapshot.py` → 에러 없이 빌드, 저PBR 종목 PBR overlay 후 PBR<0.5 종목이 정책 렌즈에 자동 편입.

- [ ] **Step 3: 렌더 확인** — `uv run python scripts/render_lens_dashboard.py` → 후보 카드 연결 관점에 `저PBR 밸류업` 렌즈 표시, lens 히트맵에 정책 렌즈 등장.

- [ ] **Step 4: 전체 회귀** → `uv run pytest -q` 그린.

---

## Self-Review 체크

- **Spec coverage:** LensKind.POLICY 신설✓ / 저PBR 밸류업 첫 인스턴스✓ / 큐레이션 시드 10(코드 확정)+PBR 스크린 하이브리드✓ / 일반 프레임(policy_lenses 리스트)✓ / 렌더 기존 lens 히트맵 재사용✓.
- **Isolation/additive:** 모델 enum 추가, market_insights/live merge 추가만. 매력도는 기존 lens weights 사용(별도 점수 없음). bot.py/insight_lookup 미접촉.
- **Type consistency:** policy_lens stock payload 키가 `_default_stock`/parse와 일치. lens dict가 sample_data lenses 구조(id/kind/name/conviction/direction/weights/risks)와 일치. `value_up_low_pbr` lens_id 일관.
- **Placeholder scan:** 시드 10코드 ticker cache로 확정. 테스트 픽스처 기존 인라인 패턴 신규작성.

## Cross-model review 예정
(b) Codex plan 리뷰 → 머지 → Codex 구현 → (a) Opus code 리뷰.

## Cross-model review 반영 v2 (2026-06-06, Codex leg) — **본 섹션이 위 태스크 본문에 우선**

Codex 리뷰: blocker 0, should-fix 2 + nit 1. 시드 10코드 전부 정확 확인(460860=동국제강, ≠001230 동국홀딩스). 반영:

- **G-01 (Task 4 통합 테스트):** lens_ids 변이만이 아니라 **screeners linked_lenses 해소까지** 검증. `build_market_insights_payload`→overlay→`parse_dashboard_input`→`build_dashboard` 경로로 PBR<0.5 종목의 candidate.linked_lenses에 "저PBR 밸류업"(name)이 실재하는지 assert. (payload lenses에 정책 렌즈가 있어야 linked로 잡히므로 end-to-end 가드.)
- **G-02 (insight_lookup 누출 차단):** `insight_lookup._build_index`가 `build_market_insights_payload(include_kr_screen=False)`를 호출 → policy lens/시드를 항상 추가하면 Telegram 인사이트 조회에 저PBR 시드가 새어나감. **`build_market_insights_payload`에 `include_policy_lens: bool = True` 플래그 추가**(Plan 4 `include_kr_screen` 동형), `insight_lookup`은 `include_policy_lens=False`로 호출. 기존 insight_lookup 테스트 회귀 확인. (bot.py/insight_lookup 본문은 호출 인자만 바뀜 — 로직 미변경.)
- **G-03 (nit, 픽스처):** `_payload_with_policy_lens()`는 인라인으로 최소 payload(as_of, price_time, market_indicators=[], lenses=[정책 렌즈 1개], stocks=[]) 구조를 직접 정의(없는 헬퍼 import 금지).

## 다음 Plan (전체 dashboard 고도화 완료 후)
v1.1 백로그: 정책 렌즈 추가 인스턴스(IRA·CHIPS·K-방산), 자사주/배당 catalyst, 진짜 외국인 순매수(네이버), KRX OPEN API 권위값, KR 실적일, 회사 가이던스(guidance_delta).
