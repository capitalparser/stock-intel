# Valuation Expectations — forward P/E vs 성장·현금 (Plan 6 / lens-dashboard 고도화)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans. 체크박스로 추적.
>
> **모든 명령:** `cd /Users/kjun/vault/01_Projects/04_stock_intel` 후 `uv run ...`.

**Goal:** 후보에 **밸류에이션 기대치** 렌즈를 더한다 — "주가가 forward 성장·현금이 받쳐주는 것보다 큰 기대를 이미 반영했나"를 forward P/E vs 성장·FCF로 판정(6-label)하고, **trailing 가치평가와 별개 섹션 + 카드 배지**로 노출한다. **매력도 점수(숫자)는 바꾸지 않는다.** (초기 `docs/superpowers/plans/2026-06-04-forward-pe-vs-guidance-dashboard.md` 스펙을 현재 아키텍처에 흡수.)

**Architecture:** 새 `dashboard/valuation_expectations.py`(순수 verdict 엔진) + provider(yfinance `.info` forward 필드, KR은 `.KS` suffix, graceful degrade). snapshot이 ticker별 valuation overlay carry → live 주입 → render 별도 섹션 `밸류에이션 기대치 점검`(듀얼 국면 다음) + 후보 카드 verdict 배지. trailing valuation(5지표)·매력도와 독립.

**Tech Stack:** Python 3.12, yfinance(기존, `.info`), 기존 `dashboard/` 패키지, pytest. 추가 외부 의존 없음. 회사 가이던스 소스 부재 → guidance_delta는 v1 데이터 부족.

**근거:** [CONTEXT.md](../../../CONTEXT.md) `밸류에이션 기대치`·`기대치 판정`·`라벨 네임스페이스 분리`, Plan 1~5(머지됨), forward-pe 스펙.

**yfinance .info 실측 필드(2026-06-06 probe):** `forwardPE`(US·KR ✓), `revenueGrowth`(비율), `earningsGrowth`(비율), `ebitdaMargins`, `freeCashflow`, `marketCap`, `totalRevenue`, `numberOfAnalystOpinions`, `recommendationKey`. KR은 `{6자리}.KS`.

---

## Scope

### 포함
- `dashboard/valuation_expectations.py` 신규 — 순수 verdict 엔진(`expectation_verdict`, `_growth_adjusted_multiple`, `_fcf_band`).
- `dashboard/providers/valuation.py` 신규 — `fetch_valuation(ticker)` (yfinance `.info`, KR `.KS`, graceful degrade).
- `dashboard/models.py` — `ValuationExpectation` dataclass + `DashboardInput`/`Dashboard`에 `valuation_expectations: list` (별도, 후보 metrics와 분리).
- `dashboard/snapshot.py` — injectable valuation overlay carry(ticker별).
- `dashboard/live.py` — valuation_expectations payload 전달 + 후보에 verdict 배지용 필드.
- `dashboard/render.py` — `밸류에이션 기대치 점검` 섹션(md+html, 듀얼 국면 다음) + 후보 카드 verdict 배지.
- 테스트.

### 비범위 (v1.1)
- **회사 가이던스 midpoint vs 컨센서스 revenue**(guidance_delta) — yfinance 미제공 → v1 데이터 부족. 실적 릴리스 파싱은 v1.1.
- estimate-revision 이력(revision_direction) — yfinance .info 직접 미제공 → v1은 `recommendationKey`/`earningsGrowth` 부호의 약한 프록시 또는 생략.
- forward EV/EBITDA fallback, DCF.
- 정책 렌즈(Plan 7).

---

## 기대치 판정 (6-label, 가용 데이터 적응)

inputs: `forward_pe`, `rev_growth_pct`, `eps_growth_pct`, `fcf_margin_pct`, (optional) `revision_dir`.
- `growth_adjusted_multiple = forward_pe / max(eps_growth_pct, rev_growth_pct*0.5)` (분모 ≤0이면 None).
  - <0.8 supportable / 0.8–1.4 balanced / 1.4–2.2 burden / >2.2 high burden.
- `fcf_margin`: ≥30 strong / 15–30 acceptable / <15 weak.

verdict 규칙(위→아래 우선):
- `데이터 부족`: forward_pe None **또는** 성장(eps·rev 둘 다) None.
- `위험`: revision_dir=="down" **또는** 성장 음수, 그런데 forward_pe 높음(≥ 동종 통념 또는 절대 고배수).
- `과열`: growth_adjusted_multiple > 2.2 (성장 대비 배수 과다).
- `기대치 부담`: 1.4 < growth_adjusted_multiple ≤ 2.2.
- `저평가 후보`: growth_adjusted_multiple < 0.8 **이고** 성장 양수.
- `정당화 가능`: 그 외(balanced 0.8–1.4) + fcf weak 아님.

각 verdict에 `expectation_read`(한 줄 설명) 동반(black-box 금지). guidance/revision 미가용은 read에 `가이던스/리비전 데이터 부족` 명시.

---

## File Structure

| 파일 | 책임 | 신규/수정 |
|---|---|---|
| `dashboard/valuation_expectations.py` | 순수 verdict 엔진 | 신규 |
| `dashboard/providers/valuation.py` | yfinance .info forward fetch + degrade | 신규 |
| `dashboard/models.py` | ValuationExpectation + payload 필드 | 수정(추가) |
| `dashboard/snapshot.py` | valuation overlay carry | 수정 |
| `dashboard/live.py` | payload 전달 + 카드 verdict | 수정 |
| `dashboard/render.py` | 밸류에이션 기대치 섹션 + 배지 | 수정 |
| tests/test_valuation_expectations.py 외 | | 신규/수정 |

---

## 핵심 계약 (시그니처 고정)

```python
# dashboard/valuation_expectations.py
def _growth_adjusted_multiple(forward_pe, eps_growth_pct, rev_growth_pct) -> float | None
def _fcf_band(fcf_margin_pct) -> str   # "strong"|"acceptable"|"weak"|"unknown"
def expectation_verdict(*, forward_pe, rev_growth_pct, eps_growth_pct, fcf_margin_pct,
                        revision_dir=None) -> dict
#   -> {"verdict": str(6-label), "read": str, "growth_adjusted_multiple": float|None,
#       "fcf_band": str, "data_gaps": list[str]}

# dashboard/providers/valuation.py
def fetch_valuation(ticker: str) -> dict
#   -> {"ticker","forward_pe","rev_growth_pct","eps_growth_pct","fcf_margin_pct",
#       "analyst_n", "recommendation", **expectation_verdict(...)} or {"ticker","verdict":"데이터 부족",...}
```

---

## Task 1: 순수 verdict 엔진

**Files:** Create `dashboard/valuation_expectations.py`, `tests/test_valuation_expectations.py`

- [ ] **Step 1: 실패 테스트** — `tests/test_valuation_expectations.py`

```python
from dashboard.valuation_expectations import (
    _fcf_band,
    _growth_adjusted_multiple,
    expectation_verdict,
)


def test_growth_adjusted_multiple_uses_max_of_eps_and_half_rev():
    # max(eps 20, rev 80*0.5=40)=40 -> 36/40 = 0.9
    assert round(_growth_adjusted_multiple(36.0, 20.0, 80.0), 3) == 0.9


def test_growth_adjusted_multiple_none_when_no_growth():
    assert _growth_adjusted_multiple(36.0, 0.0, 0.0) is None
    assert _growth_adjusted_multiple(None, 20.0, 80.0) is None


def test_fcf_band():
    assert _fcf_band(40) == "strong"
    assert _fcf_band(20) == "acceptable"
    assert _fcf_band(5) == "weak"
    assert _fcf_band(None) == "unknown"


def test_verdict_data_missing_without_forward_pe():
    out = expectation_verdict(forward_pe=None, rev_growth_pct=80, eps_growth_pct=45, fcf_margin_pct=46)
    assert out["verdict"] == "데이터 부족"


def test_verdict_overheated_when_multiple_far_exceeds_growth():
    # forward_pe 90, eps 30 -> gam 3.0 > 2.2 -> 과열
    out = expectation_verdict(forward_pe=90.0, rev_growth_pct=20, eps_growth_pct=30, fcf_margin_pct=20)
    assert out["verdict"] == "과열"


def test_verdict_burden_band():
    # forward_pe 36, eps 20 -> gam 1.8 -> 기대치 부담
    out = expectation_verdict(forward_pe=36.0, rev_growth_pct=10, eps_growth_pct=20, fcf_margin_pct=46)
    assert out["verdict"] == "기대치 부담"


def test_verdict_undervalued():
    # forward_pe 8, eps 30 -> gam 0.27 < 0.8, 성장 양수 -> 저평가 후보
    out = expectation_verdict(forward_pe=8.0, rev_growth_pct=20, eps_growth_pct=30, fcf_margin_pct=35)
    assert out["verdict"] == "저평가 후보"


def test_verdict_risk_when_revision_down_and_elevated_pe():
    out = expectation_verdict(forward_pe=45.0, rev_growth_pct=5, eps_growth_pct=5,
                              fcf_margin_pct=10, revision_dir="down")
    assert out["verdict"] == "위험"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_valuation_expectations.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현** — `dashboard/valuation_expectations.py`

```python
"""Valuation-expectations verdict engine (Plan 6). 순수·결정적.

forward P/E vs 성장·FCF로 6-label 기대치 판정. trailing 가치평가/매력도와 독립.
회사 가이던스(guidance_delta)·estimate-revision 이력은 v1 비가용 → data_gaps로 표기.
"""

from __future__ import annotations

_HIGH_ABS_PE = 40.0  # 절대 고배수 통념(위험/과열 판정 보조)


def _growth_adjusted_multiple(forward_pe, eps_growth_pct, rev_growth_pct) -> float | None:
    if forward_pe is None or forward_pe <= 0:
        return None
    eps = eps_growth_pct if eps_growth_pct is not None else 0.0
    rev = rev_growth_pct if rev_growth_pct is not None else 0.0
    denom = max(eps, rev * 0.5)
    if denom <= 0:
        return None
    return forward_pe / denom


def _fcf_band(fcf_margin_pct) -> str:
    if fcf_margin_pct is None:
        return "unknown"
    if fcf_margin_pct >= 30:
        return "strong"
    if fcf_margin_pct >= 15:
        return "acceptable"
    return "weak"


def _has_growth(eps, rev) -> bool:
    return (eps is not None) or (rev is not None)


def expectation_verdict(*, forward_pe, rev_growth_pct, eps_growth_pct,
                        fcf_margin_pct, revision_dir=None) -> dict:
    gaps: list[str] = ["가이던스 데이터 부족(yfinance 미제공)"]
    if revision_dir is None:
        gaps.append("리비전 방향 데이터 부족")
    gam = _growth_adjusted_multiple(forward_pe, eps_growth_pct, rev_growth_pct)
    fcf = _fcf_band(fcf_margin_pct)

    if forward_pe is None or not _has_growth(eps_growth_pct, rev_growth_pct):
        return _result("데이터 부족", "forward P/E 또는 성장 데이터 미연결", gam, fcf, gaps)

    growth_neg = (eps_growth_pct is not None and eps_growth_pct < 0) or \
                 (rev_growth_pct is not None and rev_growth_pct < 0)
    if (revision_dir == "down" or growth_neg) and forward_pe >= _HIGH_ABS_PE:
        return _result("위험", "이익 추정 하향/역성장 중 고배수 — 하방 위험", gam, fcf, gaps)

    if gam is not None and gam > 2.2:
        return _result("과열", "성장 대비 배수가 과도(growth-adjusted > 2.2)", gam, fcf, gaps)
    if gam is not None and gam > 1.4:
        return _result("기대치 부담", "성장은 있으나 주가가 더 큰 서프라이즈를 요구하는 구간", gam, fcf, gaps)
    if gam is not None and gam < 0.8 and not growth_neg:
        return _result("저평가 후보", "성장 대비 배수가 낮아 재평가 여지", gam, fcf, gaps)
    if fcf == "weak":
        return _result("기대치 부담", "밸류 균형이나 현금창출 약함 — 질 확인 필요", gam, fcf, gaps)
    return _result("정당화 가능", "성장·현금이 현재 배수를 대체로 정당화하는 구간", gam, fcf, gaps)


def _result(verdict, read, gam, fcf, gaps) -> dict:
    return {
        "verdict": verdict,
        "read": read + (" · 가이던스/리비전 데이터 부족" if gaps else ""),
        "growth_adjusted_multiple": (round(gam, 2) if gam is not None else None),
        "fcf_band": fcf,
        "data_gaps": gaps,
    }
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_valuation_expectations.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add dashboard/valuation_expectations.py tests/test_valuation_expectations.py
git commit -m "feat(valuation): expectation verdict engine (forward P/E vs growth/FCF)"
```

---

## Task 2: provider — yfinance .info forward fetch

**Files:** Create `dashboard/providers/valuation.py`, `tests/test_valuation_provider.py`

`fetch_valuation(ticker)`: KR(6자리)→`{ticker}.KS`, US→그대로. yfinance `.info`에서 forwardPE/revenueGrowth/earningsGrowth/ebitdaMargins/freeCashflow/totalRevenue/numberOfAnalystOpinions/recommendationKey. fcf_margin = freeCashflow/totalRevenue*100(가능 시). 비율 필드는 *100. 실패/필드없음 → verdict "데이터 부족". yfinance는 monkeypatch.

- [ ] **Step 1: 실패 테스트** — `tests/test_valuation_provider.py`

```python
import sys
from types import SimpleNamespace

from dashboard.providers.valuation import fetch_valuation


def _fake_yf(info):
    return SimpleNamespace(Ticker=lambda t: SimpleNamespace(info=info))


def test_fetch_valuation_us_maps_fields(monkeypatch):
    info = {"forwardPE": 16.4, "revenueGrowth": 0.85, "earningsGrowth": 2.1,
            "freeCashflow": 46e9, "totalRevenue": 100e9, "ebitdaMargins": 0.65,
            "numberOfAnalystOpinions": 58, "recommendationKey": "strong_buy"}
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(info))
    out = fetch_valuation("NVDA")
    assert out["forward_pe"] == 16.4
    assert round(out["rev_growth_pct"], 1) == 85.0
    assert out["fcf_margin_pct"] == 46.0  # 46e9/100e9*100
    assert out["verdict"] in {"정당화 가능", "저평가 후보", "기대치 부담", "과열", "위험"}


def test_fetch_valuation_kr_uses_ks_suffix(monkeypatch):
    captured = {}

    def Ticker(t):
        captured["sym"] = t
        return SimpleNamespace(info={"forwardPE": 5.8, "revenueGrowth": 0.69,
                                     "earningsGrowth": 4.9, "freeCashflow": 1e12,
                                     "totalRevenue": 3e12, "numberOfAnalystOpinions": 37,
                                     "recommendationKey": "buy"})

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=Ticker))
    out = fetch_valuation("005930")
    assert captured["sym"] == "005930.KS"
    assert out["forward_pe"] == 5.8


def test_fetch_valuation_degrades_to_data_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf({}))
    out = fetch_valuation("NVDA")
    assert out["verdict"] == "데이터 부족"
```

- [ ] **Step 2: 실패 확인** → FAIL (ModuleNotFoundError)

- [ ] **Step 3: 구현** — `dashboard/providers/valuation.py`

```python
"""Valuation provider: yfinance .info forward fields -> expectation verdict."""

from __future__ import annotations

from dashboard.providers.base import classify_market
from dashboard.valuation_expectations import expectation_verdict


def _pct(v):
    return None if v is None else float(v) * 100


def _yf_symbol(ticker: str) -> str:
    return f"{ticker}.KS" if classify_market(ticker) == "KR" else ticker


def fetch_valuation(ticker: str) -> dict:
    base = {"ticker": ticker}
    try:
        import yfinance as yf

        info = yf.Ticker(_yf_symbol(ticker)).info or {}
    except Exception:  # pragma: no cover - network/degrade
        info = {}

    forward_pe = info.get("forwardPE")
    rev = _pct(info.get("revenueGrowth"))
    eps = _pct(info.get("earningsGrowth"))
    fcf = info.get("freeCashflow")
    rev_total = info.get("totalRevenue")
    fcf_margin = (float(fcf) / float(rev_total) * 100) if (fcf and rev_total) else None

    verdict = expectation_verdict(
        forward_pe=(float(forward_pe) if forward_pe else None),
        rev_growth_pct=rev, eps_growth_pct=eps, fcf_margin_pct=fcf_margin,
    )
    return {
        **base,
        "forward_pe": (round(float(forward_pe), 1) if forward_pe else None),
        "rev_growth_pct": (round(rev, 1) if rev is not None else None),
        "eps_growth_pct": (round(eps, 1) if eps is not None else None),
        "fcf_margin_pct": (round(fcf_margin, 1) if fcf_margin is not None else None),
        "analyst_n": info.get("numberOfAnalystOpinions"),
        "recommendation": info.get("recommendationKey"),
        **verdict,
    }
```

- [ ] **Step 4: 통과 + 회귀** → 전체 그린

- [ ] **Step 5: 커밋**

```bash
git add dashboard/providers/valuation.py tests/test_valuation_provider.py
git commit -m "feat(valuation): yfinance .info forward-field provider (KR .KS, degrade)"
```

---

## Task 3: 모델 — ValuationExpectation + payload 필드

**Files:** Modify `dashboard/models.py`, `tests/test_dashboard_models.py`

`ValuationExpectation` frozen dataclass(ticker, forward_pe, rev_growth_pct, eps_growth_pct, fcf_margin_pct, verdict, read, data_gaps). `DashboardInput`/`Dashboard`에 `valuation_expectations: list | None = None`. `parse_dashboard_input`이 `payload.get("valuation_expectations")` 파싱(별도 — 후보 metrics 불변). 후보 카드 배지용으로 Candidate에 `expectation_verdict: str = ""` 추가(verdict 문자열만; 매력도 점수 불변).

- [ ] **Step 1: 실패 테스트(추가)** — `tests/test_dashboard_models.py` (기존 인라인 패턴)

```python
def test_parse_valuation_expectations_and_candidate_verdict():
    from dashboard.models import parse_dashboard_input
    payload = _payload_with_valuation(
        ve=[{"ticker": "NVDA", "forward_pe": 16.4, "verdict": "정당화 가능", "read": "…", "data_gaps": []}],
        stock_verdict="정당화 가능")
    parsed = parse_dashboard_input(payload)
    assert parsed.valuation_expectations[0].verdict == "정당화 가능"
    assert parsed.stocks[0].expectation_verdict == "정당화 가능"
```

> `_payload_with_valuation`은 기존 test_dashboard_models.py 인라인 payload 패턴으로 신규 작성.

- [ ] **Step 2~5:** 모델 추가 → parse → screeners가 Candidate에 `expectation_verdict=stock.expectation_verdict` 전달 → 통과/회귀 → 커밋.

```bash
git commit -m "feat(valuation): ValuationExpectation model + candidate verdict field (score unchanged)"
```

---

## Task 4: snapshot carry (injectable)

**Files:** Modify `dashboard/snapshot.py`, `tests/test_snapshot.py`

`build_snapshot(..., valuation: Callable[[str], dict] = fetch_valuation)`. 결과를 `snapshot["valuation_expectations"]`(ticker별 dict 리스트)로 + 각 stock dict에 `"expectation_verdict": ve["verdict"]`. try/except degrade.

- [ ] TDD: fake valuation 주입 → snapshot에 valuation_expectations + stock expectation_verdict 검증 → 커밋.

```bash
git commit -m "feat(valuation): snapshot carries valuation expectations + candidate verdict"
```

---

## Task 5: live overlay

**Files:** Modify `dashboard/live.py`, `tests/test_live.py`

`overlay_snapshot`이 `snapshot["valuation_expectations"]`를 `payload["valuation_expectations"]`로 복사, `_overlay_stock`이 `expectation_verdict`를 stock에 + evidence 한 줄(`밸류에이션 기대치: {verdict}`).

- [ ] TDD → 커밋.

```bash
git commit -m "feat(valuation): thread valuation expectations through live overlay"
```

---

## Task 6: render — 밸류에이션 기대치 점검 섹션 + 배지

**Files:** Modify `dashboard/render.py`, `tests/test_dashboard_render.py`

- md+html에 `밸류에이션 기대치 점검` 섹션(**듀얼 국면 다음, 후보 위**): 표(종목·Forward P/E·성장·FCF·기대치 판정). top expectation-risk(과열/위험/기대치 부담) 우선.
- 후보 카드에 verdict 배지(과열/위험=경고색 `.hbadge.bbad`, 기대치 부담=`.bneu`, 저평가 후보/정당화 가능=양호색). 기존 배지 스타일 재사용.
- 기계용어 노출 금지(한글 라벨), 데이터 부족은 `데이터 부족` 표기.

- [ ] TDD(기존 render 픽스처 패턴 신규작성): 섹션 제목·verdict 문자열 md+html assert → 커밋.

```bash
git commit -m "feat(valuation): render valuation-expectations section + candidate verdict badge"
```

---

## Task 7: 라이브 스모크

- [ ] `set -a; source .env; set +a; uv run python scripts/build_dashboard_snapshot.py` → 에러 없이 valuation_expectations 생성(US·KR forward_pe 채워짐, 일부 데이터 부족 degrade).
- [ ] `uv run python scripts/render_lens_dashboard.py` → 밸류에이션 기대치 섹션 + 카드 배지.
- [ ] `uv run pytest -q` 전체 그린.

---

## Self-Review 체크

- **Spec coverage:** forward P/E·성장·FCF 6-label✓ / yfinance .info(US·KR .KS)✓ / 별도 섹션+카드 배지✓ / **매력도 점수 불변**(별도 payload, Candidate verdict는 문자열만)✓ / guidance·revision 데이터 부족 명시✓ / degrade✓.
- **Isolation/additive:** valuation은 독립 payload·필드. trailing 5지표/매력도 미접촉. bot.py/insight_lookup 미접촉.
- **Type consistency:** `expectation_verdict`/`fetch_valuation` 반환 dict 키 snapshot→live→render 일관. 6-label이 CONTEXT 기대치 판정과 동일.
- **Placeholder scan:** yfinance 필드명 probe로 확정(forwardPE/revenueGrowth/earningsGrowth/freeCashflow/totalRevenue/ebitdaMargins/numberOfAnalystOpinions/recommendationKey). 테스트 픽스처 기존 패턴 신규작성 명시.

## Cross-model review 예정
(b) Codex plan 리뷰 → 머지 → Codex 구현 → (a) Opus code 리뷰.

## 다음 Plan
Plan 7 정책 렌즈(저PBR 밸류업, LensKind.POLICY). v1.1: 회사 가이던스 파싱(guidance_delta), estimate-revision 이력, forward EV/EBITDA.
