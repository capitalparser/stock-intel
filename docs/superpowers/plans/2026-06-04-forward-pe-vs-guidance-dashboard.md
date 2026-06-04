# Forward P/E vs Guidance Dashboard Implementation Plan

> **For agentic workers:** This is a planning-only handoff. Do not implement from this document until the active dashboard work in other sessions is reconciled. When implementation starts, use `superpowers:subagent-driven-development` or `superpowers:executing-plans` and update checkboxes task-by-task.

**Goal:** Add a valuation expectations layer to the stock intelligence dashboard that compares each AI-infrastructure candidate's forward valuation multiple against current company guidance, consensus revisions, and cash-flow quality.

**Decision Frame:** The dashboard should answer: "Is the current price already discounting more growth than management guidance and sell-side revisions support?"

**Architecture:** Extend the existing dashboard model with a separate `valuation_expectations` payload. Keep it independent from candidate scoring in v1. Render it as a new section beside or below the macro state cockpit, not as a replacement for existing cards.

**Tech Stack:** Python 3.12, existing `dashboard/` package, snapshot/cache pattern, pytest, HTML/Markdown renderer, external data adapters deferred behind provider interfaces.

---

## Scope

### Included

- AI infrastructure and adjacent beneficiaries universe:
  - Core AI semis: `NVDA`, `AVGO`, `AMD`, `MRVL`, `TSM`, `MU`
  - AI server/storage/networking: `DELL`, `SMCI`, `HPE`, `WDC`, `ANET`
  - Power/data-center infrastructure: `VRT`, `ETN`, `GEV`, `CEG`, `NEE`, `TLN`
  - Korea AI chain when available: `005930`, `000660`, `042700`, `034020`, `267260`, `298040`
- Forward valuation fields:
  - forward P/E
  - forward revenue growth
  - forward EPS or EBITDA growth
  - FCF margin
  - latest guidance revenue range or midpoint
  - consensus revenue/EPS estimate
  - post-earnings revision direction
- Reader-facing verdict labels:
  - `정당화 가능`
  - `기대치 부담`
  - `과열`
  - `위험`
  - `저평가 후보`
  - `데이터 부족`

### Deferred

- Automated scraping of every earnings transcript.
- Full financial model or DCF.
- Buy/sell recommendation language.
- Candidate score rewiring.
- Intraday options/flow interpretation.
- Any code change while another agent is modifying dashboard internals.

---

## Data Contract

Add a structured payload shaped like:

```python
{
    "valuation_expectations": [
        {
            "ticker": "AVGO",
            "company": "Broadcom",
            "as_of": "2026-06-04",
            "forward_pe": 36.5,
            "revenue_growth_guide_pct": 84.0,
            "eps_growth_est_pct": 45.0,
            "ebitda_margin_pct": 69.0,
            "fcf_margin_pct": 46.0,
            "guidance_revenue_midpoint": 29.4,
            "consensus_revenue": 28.6,
            "consensus_eps": 2.45,
            "revision_direction": "pending",
            "ai_exposure": "ASIC / AI networking",
            "expectation_read": "AI 성장률은 매우 강하지만 주가는 더 큰 서프라이즈를 요구하는 구간",
            "verdict": "기대치 부담",
            "source_refs": ["Broadcom FY2026 Q2 release", "consensus provider"],
            "data_gaps": ["forward_pe provider 연결 필요", "post-earnings revision 반영 전"],
        }
    ]
}
```

Required field behavior:

- Missing valuation data must render as `데이터 부족`, not zero.
- Consensus source must be named in `source_refs`.
- If guidance is unavailable, use latest reported growth plus explicit `guidance gap`.
- Korea tickers should keep Korean company name primary and code secondary, following the existing dashboard rendering rule.

---

## Core Metrics

### 1. Forward Multiple

Primary:

```text
forward_pe = current_price / next_fiscal_year_consensus_eps
```

Fallback:

```text
forward_ev_ebitda = enterprise_value / next_fiscal_year_consensus_ebitda
```

Use fallback only when EPS is not meaningful.

### 2. Guidance Beat / Miss

```text
guidance_delta_pct = (guidance_midpoint - consensus_revenue) / consensus_revenue * 100
```

Classification:

- `strong beat`: `>= +3%`
- `modest beat`: `+0.5% to +3%`
- `in line`: `-0.5% to +0.5%`
- `miss`: `< -0.5%`

### 3. Multiple-To-Growth Burden

Suggested first-pass heuristic:

```text
growth_adjusted_multiple = forward_pe / max(eps_growth_est_pct, revenue_growth_guide_pct * 0.5)
```

Classification:

- `< 0.8`: valuation may be supportable
- `0.8-1.4`: balanced
- `1.4-2.2`: expectation burden
- `> 2.2`: high expectation burden

This is intentionally a screen, not a valuation conclusion.

### 4. Cash Conversion

Use FCF margin and EBITDA margin to distinguish real AI monetization from revenue-only growth.

Classification:

- FCF margin `>= 30%`: strong
- `15-30%`: acceptable
- `< 15%`: weak or capex-heavy

---

## Verdict Logic

Initial deterministic rules:

```text
정당화 가능:
  forward_pe high but revenue_growth_guide_pct strong, EPS/EBITDA growth strong,
  FCF margin strong, and revision_direction not negative.

기대치 부담:
  growth is strong but multiple-to-growth burden is high, or guidance beat is
  modest while the stock had a strong pre-earnings run.

과열:
  forward_pe very high, guidance_delta_pct in line or miss, and revision_direction
  flat/down.

위험:
  guidance miss or revision down while forward_pe remains elevated.

저평가 후보:
  forward_pe moderate/low, guidance_delta_pct positive, revision_direction up.

데이터 부족:
  missing forward multiple or guidance/consensus comparison.
```

Add explanatory text alongside the verdict so the dashboard does not look like a black-box score.

---

## UI Placement

Recommended section title:

```text
밸류에이션 기대치 점검
```

Place after `매크로 현재 상태` and before `후보별 판단 메모`.

Required table columns:

- 종목
- Forward P/E
- 가이던스 성장
- 컨센서스 대비
- FCF 전환
- Revision
- 기대치 판단

Required card fields for top 5 expectation-risk names:

- primary label: ticker or Korean company name
- current verdict
- one-line expectation read
- forward P/E
- guidance delta
- FCF margin
- data gaps

Design constraint:

- Do not make it a separate landing page.
- Do not use raw JSON or provider field names in the primary UI.
- Keep Korean reader-facing labels.

---

## File Impact Plan

Implementation should touch only these files unless a blocker is documented:

- Create `dashboard/valuation_expectations.py`
- Create `tests/test_valuation_expectations.py`
- Modify `dashboard/models.py`
- Modify `dashboard/live.py`
- Modify `dashboard/render.py`
- Modify `dashboard/sample_data.py`
- Modify `tests/test_dashboard_models.py`
- Modify `tests/test_dashboard_render.py`

Do not modify:

- `alert_server.py`
- `bot.py`
- `dashboard/insight_lookup.py`
- `scripts/inject_lazy.py`

Those files are currently part of separate work and should be treated as collision surfaces.

---

## Task Plan

### Task 1: Data Model

- [ ] Add `ValuationExpectation` dataclass.
- [ ] Add optional `valuation_expectations` field to `DashboardInput` and `Dashboard`.
- [ ] Parse missing values as `None`.
- [ ] Preserve existing dashboard payload compatibility.

Acceptance:

- Existing sample payloads parse without valuation data.
- New payload with AVGO valuation expectation parses.

### Task 2: Deterministic Verdict Engine

- [ ] Create `dashboard/valuation_expectations.py`.
- [ ] Implement `guidance_delta_pct`.
- [ ] Implement multiple-to-growth burden classification.
- [ ] Implement verdict assignment.
- [ ] Emit explicit `data_gaps`.

Acceptance:

- AVGO-like case with strong growth but high multiple returns `기대치 부담`.
- Missing forward P/E returns `데이터 부족`.
- Guidance miss with high multiple returns `위험` or `과열`.

### Task 3: Sample Seed

- [ ] Add deterministic sample records for `AVGO`, `NVDA`, `AMD`, `TSM`, `MRVL`.
- [ ] Include one Korean record such as `000660` or `005930`.
- [ ] Mark provider-dependent values as sample unless sourced from current snapshot.

Acceptance:

- Sample dashboard renders valuation section without live providers.

### Task 4: Live Overlay

- [ ] Add provider hook but keep failure graceful.
- [ ] Merge valuation payload by ticker.
- [ ] Preserve source refs and data gaps.

Acceptance:

- Live dashboard still renders when provider is unavailable.
- Missing consensus data does not block report generation.

### Task 5: Renderer

- [ ] Render `밸류에이션 기대치 점검` section.
- [ ] Add compact table.
- [ ] Add top expectation-risk cards.
- [ ] Use Korean company-name-first rule for domestic stocks.

Acceptance:

- HTML contains valuation section.
- Markdown contains compact valuation briefing.
- No raw implementation terms appear in UI.

### Task 6: Tests and Verification

- [ ] Add model parsing tests.
- [ ] Add verdict engine tests.
- [ ] Add HTML/Markdown render tests.
- [ ] Run focused tests.
- [ ] Run full `uv run pytest -q`.
- [ ] Regenerate dashboard report only after implementation conflicts are cleared.

---

## Source Requirements

Minimum source hierarchy:

1. Company earnings release or 10-Q/8-K for reported results and guidance.
2. Earnings transcript for management commentary.
3. Named consensus provider for estimates and revisions.
4. Market data provider for current price and forward multiple.

If source 3 or 4 is not available locally, mark the row as `데이터 부족` rather than inventing numbers.

---

## Collision Guard

Before implementation:

- [ ] Check `git status --short`.
- [ ] Confirm no active edits in `dashboard/render.py`, `dashboard/models.py`, or `dashboard/live.py` from another agent.
- [ ] If those files are dirty, stop and reconcile before editing.
- [ ] Stage only valuation expectation files.
- [ ] Do not commit unrelated dirty files.

---

## Initial Manual Analysis Rule

Until provider integration is complete, do not present the dashboard section as fully live. Use one of:

- `sample`
- `manual_source_backed`
- `live_partial`
- `live_verified`

The report header or section subtitle should show this status.

