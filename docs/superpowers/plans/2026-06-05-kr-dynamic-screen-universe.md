# KR Dynamic Screen → Candidate Universe (Plan 4 / lens-dashboard 고도화)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans. 체크박스로 추적.
>
> **모든 명령:** `cd /Users/kjun/vault/01_Projects/04_stock_intel` 후 `uv run ...`.

**Goal:** 국장(KRX) 후보를 상황판 candidate universe의 1급 시민으로 올린다 — `signals/kr_watch_candidates.py`의 섹터 시드를 dashboard stock payload로 변환해 US 큐레이션과 합집합(union)하고, 스냅샷이 기존 KR provider로 실데이터를 overlay하게 한다. 방금 만든 KR 듀얼 국면이 판정할 국장 후보가 생긴다.

**Architecture:** 순수 변환 + 병합. 새 `dashboard/kr_universe.py`가 `KR_CANDIDATE_SEEDS`(이미 존재)를 stock dict로 변환한다(ticker `KRX:000660`→`000660`, 섹터→lens 매핑, notes→thesis/evidence). `market_insights.build_market_insights_payload`가 이를 큐레이션 stocks와 ticker 기준 dedup-merge한다. 스코어링은 기존 dashboard 5-metric 매력도가 담당(스크리너 total_score를 매력도에 섞지 않음 — 별개 신호). 감사인 독립성·수급·공매도 주입은 Plan 5(봇 시그니처).

**Tech Stack:** Python 3.12, 기존 `dashboard/`·`signals/` 패키지, pytest. 추가 외부 의존 없음(순수 변환; 실데이터는 기존 snapshot 경로 재사용).

**근거:** [CONTEXT.md](../../../CONTEXT.md) `후보 universe (Candidate Universe)` 용어, Plan 1·2(매크로 듀얼 국면, 머지됨).

---

## Scope

### 포함
- `dashboard/kr_universe.py` 신규 — `KR_SECTOR_LENS` 매핑 + `seeds_to_stocks(seeds)` 순수 변환.
- `dashboard/market_insights.py` 수정 — `build_market_insights_payload`가 KR 시드 stocks를 union-merge(추가만, 기존 큐레이션 보존).
- 테스트 신규/추가.

### 비범위 (다른 Plan)
- 감사인 독립성/수급/공매도 risk_flags 주입 → **Plan 5**(봇 시그니처). 본 plan은 universe 진입까지.
- 스크리너 `evaluate_candidate` total_score/watch_status를 dashboard 매력도로 흡수 → 비채택(별개 신호; 시드의 정성 점수는 evidence로만).
- catalyst(Plan 3) / 밸류에이션 기대치(Plan 6) / 정책 렌즈(Plan 7).
- KR 시드 목록 자체의 자동 확장(DART 공급계약 등) → 후속.

---

## File Structure

| 파일 | 책임 | 신규/수정 |
|---|---|---|
| `dashboard/kr_universe.py` | KR 시드 → stock dict 순수 변환 + 섹터→lens 매핑 | 신규 |
| `dashboard/market_insights.py` | KR 시드 union-merge (추가만) | 수정 |
| `tests/test_kr_universe.py` | 변환·정규화·lens 매핑 | 신규 |
| `tests/test_market_insights.py` | union-merge·dedup (기존 있으면 추가, 없으면 신규) | 수정/신규 |

---

## 핵심 계약 (시그니처 고정)

```python
# dashboard/kr_universe.py
KR_SECTOR_LENS: dict[str, list[str]]  # 섹터 -> lens_ids
def normalize_kr_ticker(symbol: str) -> str          # "KRX:000660" -> "000660"
def seed_to_stock(seed) -> dict                      # CandidateSeed -> dashboard stock payload dict
def kr_screen_stocks() -> list[dict]                 # KR_CANDIDATE_SEEDS 전체 변환
```

stock payload는 `market_insights._default_stock`와 동일 키 집합(`ticker, company, sector, lens_ids, thesis, metrics{5x50}, evidence, bull_case, bear_case, gaps, next_action, source_refs, peer_group`)을 만족해야 `parse_dashboard_input`이 파싱하고 snapshot overlay가 붙는다.

---

## Task 1: KR 시드 → stock 변환 (`kr_universe.py`)

**Files:** Create `dashboard/kr_universe.py`, `tests/test_kr_universe.py`

- [ ] **Step 1: 실패 테스트** — `tests/test_kr_universe.py`

```python
from dashboard.kr_universe import (
    KR_SECTOR_LENS,
    kr_screen_stocks,
    normalize_kr_ticker,
    seed_to_stock,
)
from signals.kr_watch_candidates import CandidateSeed


def test_normalize_strips_krx_prefix():
    assert normalize_kr_ticker("KRX:000660") == "000660"
    assert normalize_kr_ticker("000660") == "000660"


def test_seed_to_stock_shape_and_lens():
    seed = CandidateSeed("KRX:000660", "SK하이닉스", "반도체/HBM/소부장", 20, 16, "HBM/AI 메모리 대표주")
    stock = seed_to_stock(seed)
    assert stock["ticker"] == "000660"
    assert stock["company"] == "SK하이닉스"
    assert stock["sector"] == "반도체/HBM/소부장"
    assert "semiconductors" in stock["lens_ids"]
    # 필수 키(_default_stock와 동일 집합) 존재
    for key in ("metrics", "thesis", "evidence", "bull_case", "bear_case", "gaps",
                "next_action", "source_refs", "peer_group"):
        assert key in stock
    assert stock["metrics"] == {"valuation": 50, "quality": 50, "growth": 50,
                                "revision": 50, "momentum": 50}
    assert any("국장 스크린" in s for s in stock["source_refs"])
    assert "HBM/AI 메모리 대표주" in " ".join(stock["evidence"])


def test_kr_screen_stocks_covers_seeds_and_normalizes():
    stocks = kr_screen_stocks()
    tickers = {s["ticker"] for s in stocks}
    assert "000660" in tickers and "042700" in tickers
    assert all(t.isdigit() and len(t) == 6 for t in tickers)  # 전부 6자리 정규화


def test_sector_lens_map_covers_all_seed_sectors():
    from signals.kr_watch_candidates import KR_CANDIDATE_SEEDS
    seed_sectors = {s.sector for s in KR_CANDIDATE_SEEDS}
    assert seed_sectors <= set(KR_SECTOR_LENS)  # 모든 시드 섹터에 lens 매핑 존재
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_kr_universe.py -q`
Expected: FAIL — `ModuleNotFoundError: dashboard.kr_universe`

- [ ] **Step 3: 구현** — `dashboard/kr_universe.py`

```python
"""Convert KR sector screen seeds into dashboard candidate stocks (Plan 4).

순수 변환만 — 실데이터(가격/PER/지표)는 기존 snapshot overlay가 ticker로 붙인다.
감사인 독립성/수급/공매도 주입은 Plan 5(봇 시그니처). 스크리너 total_score는
dashboard 매력도에 섞지 않고 시드의 정성 점수만 evidence로 보존한다.
"""

from __future__ import annotations

import re

from signals.kr_watch_candidates import KR_CANDIDATE_SEEDS, CandidateSeed

# 섹터 -> dashboard lens_ids (기존 lens id 재사용: semiconductors / ai_power_bottleneck /
# low_per_revision / ai_agent_compute / risk_on_liquidity).
KR_SECTOR_LENS: dict[str, list[str]] = {
    "반도체/HBM/소부장": ["semiconductors"],
    "전력기기/전선/ESS/원전": ["ai_power_bottleneck"],
    "조선/방산": ["risk_on_liquidity"],
    "금융/증권/지주사": ["low_per_revision"],
    "AI 소프트웨어/플랫폼": ["ai_agent_compute"],
}

_NEUTRAL_METRICS = {"valuation": 50, "quality": 50, "growth": 50, "revision": 50, "momentum": 50}


def normalize_kr_ticker(symbol: str) -> str:
    raw = symbol.split(":", 1)[1] if ":" in symbol else symbol
    return raw.strip()


def _lens_for_sector(sector: str) -> list[str]:
    return list(KR_SECTOR_LENS.get(sector, ["risk_on_liquidity"]))


def seed_to_stock(seed: CandidateSeed) -> dict:
    ticker = normalize_kr_ticker(seed.symbol)
    lens_ids = _lens_for_sector(seed.sector)
    return {
        "ticker": ticker,
        "company": seed.name,
        "sector": seed.sector,
        "lens_ids": lens_ids,
        "thesis": f"{seed.name}: {seed.notes} (국장 스크린 섹터 {seed.sector}).",
        "metrics": dict(_NEUTRAL_METRICS),
        "evidence": [
            f"국장 스크린: thesis_fit {seed.thesis_fit}, 수주 가시성 {seed.contract_visibility}",
            seed.notes,
        ],
        "bull_case": [f"{seed.sector} 테마 시드 — {seed.notes}"],
        "bear_case": ["국장 스크린 시드 — 가격·실적·감사인 독립성 자동 검증 전이므로 테마 강도와 투자 판단 분리."],
        "gaps": [
            "국장 스크린 시드 — 실데이터(가격·수급·공매도) 스냅샷 overlay 필요",
            "감사인 독립성 차단 여부는 Plan 5(봇 시그니처)에서 주입 예정",
        ],
        "next_action": "국장 후보: 최근 가격·수급·감사인 독립성을 확인한 뒤 관찰/제외 판단.",
        "source_refs": ["국장 스크린 (kr_watch_candidates)"],
        "peer_group": seed.sector,
    }


def kr_screen_stocks() -> list[dict]:
    return [seed_to_stock(seed) for seed in KR_CANDIDATE_SEEDS]
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_kr_universe.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/kr_universe.py tests/test_kr_universe.py
git commit -m "feat(universe): convert KR sector screen seeds to dashboard stocks"
```

---

## Task 2: union-merge into market insights payload

**Files:** Modify `dashboard/market_insights.py`, `tests/test_market_insights.py`

KR 시드를 큐레이션 stocks와 ticker 기준으로 합친다. 이미 큐레이션/vault에 있는 ticker(예: `000660`)면 **중복 추가하지 않고** 기존 항목에 `source_refs`에 `국장 스크린`을 더하고 `lens_ids` 합집합만 보강(기존 thesis/metrics 보존). 신규 KR 티커는 그대로 추가.

- [ ] **Step 1: 실패 테스트** — `tests/test_market_insights.py` (없으면 신규)

```python
from dashboard.market_insights import build_market_insights_payload


def test_payload_includes_kr_screen_candidates(tmp_path):
    # 빈 insights 디렉토리 → 큐레이션 + KR 시드만.
    payload = build_market_insights_payload(insights_dir=tmp_path)
    tickers = {str(s["ticker"]) for s in payload["stocks"]}
    # 국장 시드 일부가 universe에 진입
    assert "042700" in tickers   # 한미반도체 (큐레이션에 없던 신규 KR)
    assert "267260" in tickers   # HD현대일렉트릭


def test_kr_screen_merge_dedups_existing_ticker(tmp_path):
    payload = build_market_insights_payload(insights_dir=tmp_path)
    rows = [s for s in payload["stocks"] if str(s["ticker"]) == "000660"]
    assert len(rows) == 1  # 중복 없음
    assert any("국장 스크린" in r for r in rows[0].get("source_refs", []))


def test_existing_curated_payload_still_parses(tmp_path):
    from dashboard.models import parse_dashboard_input
    payload = build_market_insights_payload(insights_dir=tmp_path)
    parsed = parse_dashboard_input(payload)  # 전체 universe 파싱 무결
    assert len(parsed.stocks) >= len({str(s["ticker"]) for s in payload["stocks"]}) - 0
```

> `000660`이 SAMPLE_DASHBOARD 큐레이션에 있는지 구현 전 확인(`grep '000660' dashboard/sample_data.py`). 없으면 `test_kr_screen_merge_dedups_existing_ticker`는 "신규 추가 후 단일 존재"로 의미가 동일하게 성립(merge 경로 대신 add 경로)하나, dedup 경로를 실제로 타게 하려면 큐레이션에 존재하는 KR 티커를 고른다(예: sample_data에 있는 KR 티커). 구현자는 sample_data의 실제 KR 티커로 테스트 티커를 맞춘다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_market_insights.py -q`
Expected: FAIL — `042700` 부재

- [ ] **Step 3: 구현** — `dashboard/market_insights.py`
  - import: `from dashboard.kr_universe import kr_screen_stocks`.
  - `build_market_insights_payload`에서 `_merge_stocks` 후 KR 시드 union 추가:

```python
def build_market_insights_payload(insights_dir=DEFAULT_MARKET_INSIGHTS_DIR) -> dict:
    payload = deepcopy(SAMPLE_DASHBOARD)
    insights = _collect_related_tickers(Path(insights_dir))
    merged = _merge_stocks(payload["stocks"], insights)
    payload["stocks"] = _merge_kr_screen(merged, kr_screen_stocks())
    return payload


def _merge_kr_screen(stocks: list[dict], kr_stocks: list[dict]) -> list[dict]:
    by_ticker = {str(s["ticker"]): s for s in stocks}
    for kr in kr_stocks:
        t = str(kr["ticker"])
        if t in by_ticker:
            existing = by_ticker[t]
            existing["source_refs"] = sorted(set(existing.get("source_refs", []) + kr["source_refs"]))
            existing["lens_ids"] = sorted(set(existing.get("lens_ids", []) + kr["lens_ids"]))
            continue
        by_ticker[t] = kr
    return sorted(by_ticker.values(), key=lambda s: str(s["ticker"]))
```

- [ ] **Step 4: 통과 + 전체 회귀**

Run: `uv run pytest tests/test_market_insights.py -q` → PASS
Run: `uv run pytest -q` → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/market_insights.py tests/test_market_insights.py
git commit -m "feat(universe): union-merge KR screen candidates into dashboard universe"
```

---

## Task 3: 라이브 스모크 + universe 확인

**Files:** (코드 변경 없음 — 검증)

- [ ] **Step 1: universe 카운트 확인 (네트워크 없이)**

Run:
```bash
uv run python -c "from dashboard.market_insights import build_market_insights_payload as b; p=b(); ks=[s for s in p['stocks'] if str(s['ticker']).isdigit() and len(str(s['ticker']))==6]; print('KR 후보:', len(ks), '/ 전체:', len(p['stocks']))"
```
Expected: KR 후보 ≥ 30 (시드 39 - 큐레이션 중복), 전체 universe가 그만큼 증가.

- [ ] **Step 2: 라이브 스냅샷 스모크 (yfinance/KR provider)**

Run: `set -a; source .env; set +a; uv run python scripts/build_dashboard_snapshot.py`
Expected: Universe 카운트가 KR 시드만큼 증가, KR 티커들이 price/PER overlay됨(일부 fetch 에러는 graceful). US/KR 국면 요약 정상 출력.

- [ ] **Step 3: 렌더 확인 (선택)**

Run: `uv run python scripts/render_lens_dashboard.py`
Expected: 상위 후보에 국장 종목이 매력도 순위에 등장(실데이터 overlay 후). 미국 편향 완화.

- [ ] **Step 4: 전체 회귀 + 커밋(문서/스모크 메모 있으면)**

Run: `uv run pytest -q` → 전체 그린.

---

## Self-Review 체크

- **Spec coverage:** KR 시드 → stock 변환✓ / ticker 정규화(KRX:→6자리)✓ / 섹터→lens 매핑✓ / union-merge + dedup✓ / 스냅샷 실데이터 overlay는 기존 경로 재사용✓ / 매력도 스코어링은 dashboard 기존(스크리너 score 미흡수)✓.
- **Isolation/additive:** market_insights는 merge 단계 추가만(기존 _merge_stocks 보존). 감사인 독립성·수급은 Plan 5로 명시 분리.
- **Type consistency:** `seed_to_stock` 출력 키가 `_default_stock`/`parse_dashboard_input` 기대 키와 일치. `kr_screen_stocks`/`normalize_kr_ticker`/`KR_SECTOR_LENS` 시그니처 태스크 간 일치.
- **Placeholder scan:** 없음. (Task 2 테스트의 dedup 티커는 sample_data 실제 KR 티커로 구현자가 확정.)

## Cross-model review 예정
Plan 1·2와 동일: (b) Codex plan 리뷰 → 차이 머지 → Codex 구현 → (a) Opus code 리뷰.

## Cross-model review 반영 v2 (2026-06-05, Codex leg) — **본 섹션이 위 태스크 본문에 우선**

Codex 리뷰: should-fix 7 + nit 4. (#6의 "blocker 4"는 TDD red 상태 오분류 — 모듈 미존재/ModuleNotFoundError는 Task 1 구현 전 의도된 빨강이라 무효. 그 안의 진짜 항목만 아래 반영.)

- **C-01 (명명 통일):** 핵심 계약·구현은 `kr_screen_stocks()`로 통일. Scope 줄의 `seeds_to_stocks(seeds)` 표현은 무시(= `kr_screen_stocks`). 별도 public `seeds_to_stocks` 만들지 말 것.
- **C-02 (미사용 import 제거):** `kr_universe.py`의 `import re` 삭제(`normalize_kr_ticker`는 `split(":")`만 사용).
- **C-03 (dedup 테스트 실재화, #3):** sample_data에는 KR 6자리 티커가 **없다**(전부 US: ON/TXN/ADI/NVDA/DELL/WDC/VRT/MPWR). 따라서 `build_market_insights_payload` 경로로는 KR dedup-merge branch가 안 탄다. dedup 테스트는 **`_merge_kr_screen`을 직접 호출**해 검증한다:
  ```python
  def test_merge_kr_screen_dedups_existing_ticker():
      from dashboard.market_insights import _merge_kr_screen
      curated = [{"ticker": "000660", "company": "SK하이닉스", "sector": "기존",
                  "lens_ids": ["semiconductors"], "source_refs": ["큐레이션"],
                  "metrics": {"valuation":50,"quality":50,"growth":50,"revision":50,"momentum":50}}]
      from dashboard.kr_universe import seed_to_stock
      from signals.kr_watch_candidates import CandidateSeed
      kr = [seed_to_stock(CandidateSeed("KRX:000660","SK하이닉스","반도체/HBM/소부장",20,16,"HBM"))]
      out = _merge_kr_screen(curated, kr)
      rows = [s for s in out if s["ticker"] == "000660"]
      assert len(rows) == 1                                  # 중복 없음(merge branch)
      assert "국장 스크린 (kr_watch_candidates)" in rows[0]["source_refs"]
      assert rows[0]["company"] == "SK하이닉스"             # 기존 항목 보존
  ```
  Task 2의 `test_payload_includes_kr_screen_candidates`(신규 add branch)는 유지.
- **C-04 (시드 카운트 정정, #4):** `KR_CANDIDATE_SEEDS`는 **40개**. Task 3 smoke expected를 "KR 후보 = 40 − (sample/vault 중복) ≈ 40"로, `≥ 30` 대신 `>= 35`로. universe per-ticker fetch ×40 추가: 라이브 스모크가 이미 universe 143을 처리하므로 하드 가드 불필요하나, **graceful degrade 의존을 Plan에 명시**(소스 실패 시 해당 종목 metrics 중립 + data_quality.errors 기록, 빌드 중단 없음). 운영상 느리면 후속에서 `scripts/build_dashboard_snapshot.py --limit` 추가(이번 비범위).
- **C-05 (overlay/ranking, #5):** KR 시드 metrics는 50 기본 + snapshot overlay가 KR provider 실데이터로 덮어쓴다. **overlay 회귀 테스트 추가**: fake KR `RawStock`(또는 snapshot dict)로 50→실점수 덮어쓰기 확인. provider 전체 실패로 50 잔존 시 ranking 왜곡 방지를 위해 — 하드 로직 대신 **`gaps`에 "실데이터 미연결"이 있으면 그 사실이 카드/순위 근거로 노출되게**(이미 live overlay가 gap 추가). 별도 강등 로직은 비범위(문서화).
- **C-06 (lens 주석, #1):** `KR_SECTOR_LENS` 주석에 "기존 7개 lens 중 5개 사용(`power_analog`·`stablecoin_rails` 제외 — KR 시드 섹터와 직접 매칭 없음)" 명시.

## 다음 Plan
Plan 5 봇 시그니처(독립성/수급/공매도 주입 — 국장 후보에 🚫 차단 배지) / Plan 3 catalyst / Plan 6 밸류에이션 기대치 / Plan 7 정책 렌즈(저PBR).
