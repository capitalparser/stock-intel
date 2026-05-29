# Lens Investment Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a v1 personal investment dashboard that renders a self-contained HTML report from same-level thesis, sector, macro, and factor lenses.

**Architecture:** Add a focused `dashboard/` package with deterministic domain models, lens scoring, candidate state assignment, and HTML/Markdown rendering. Launch with curated JSON seed data and a CLI script so the lens model and output are useful before live valuation/news APIs are added.

**Tech Stack:** Python 3.12, dataclasses, JSON files, stdlib `html`, pytest, self-contained HTML/CSS following the PAS cockpit pattern.

---

## Output Shape

The v1 user-facing artifact is a self-contained HTML dashboard:

```text
state/dashboard/reports/YYYY-MM-DD-lens-dashboard.html
```

The same renderer also returns a compact Markdown briefing so the result can later be sent through Telegram without rebuilding the core model:

```text
state/dashboard/reports/YYYY-MM-DD-lens-dashboard.md
```

The HTML dashboard is the primary 산출물. The durable asset is the structured dashboard model that powers the HTML.

## File Structure

- Create `dashboard/__init__.py`: package exports.
- Create `dashboard/models.py`: dataclasses and JSON parsing for regime, lenses, stocks, candidates, and dashboard output.
- Create `dashboard/screeners.py`: deterministic lens overlap and candidate status logic.
- Create `dashboard/render.py`: HTML and Markdown rendering.
- Create `dashboard/sample_data.py`: embedded v1 seed data loader for local use and tests.
- Create `scripts/render_lens_dashboard.py`: CLI entrypoint that writes HTML/Markdown reports.
- Create `tests/test_dashboard_models.py`: model parsing and validation tests.
- Create `tests/test_dashboard_screeners.py`: lens overlap and status tests.
- Create `tests/test_dashboard_render.py`: HTML/Markdown rendering tests.
- Modify `pyproject.toml`: include `dashboard` in hatch package list.
- Modify `README.md`: document the dashboard command and output files.

---

### Task 1: Dashboard Models

**Files:**
- Create: `dashboard/__init__.py`
- Create: `dashboard/models.py`
- Test: `tests/test_dashboard_models.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_dashboard_models.py`:

```python
from dashboard.models import (
    CandidateStatus,
    DashboardInput,
    LensKind,
    parse_dashboard_input,
)


def test_parse_dashboard_input_accepts_same_level_lenses():
    payload = {
        "as_of": "2026-05-29",
        "regime": {
            "verdict": "conditional",
            "risk_appetite": "risk-on",
            "rates": "stable",
            "dollar": "stable",
            "volatility": "low",
            "notes": ["AI infrastructure heat remains elevated"],
        },
        "lenses": [
            {
                "id": "ai_agent_compute",
                "kind": "thesis",
                "name": "AI agent compute",
                "conviction": "high",
                "direction": "improving",
                "weights": {"growth": 0.35, "revision": 0.25, "valuation": 0.15, "momentum": 0.15, "quality": 0.10},
                "risks": ["capex fatigue"],
            },
            {
                "id": "semiconductors",
                "kind": "sector",
                "name": "Semiconductors",
                "conviction": "medium",
                "direction": "stable",
                "weights": {"growth": 0.25, "revision": 0.20, "valuation": 0.25, "momentum": 0.20, "quality": 0.10},
                "risks": ["valuation stretch"],
            },
        ],
        "stocks": [
            {
                "ticker": "ON",
                "company": "ON Semiconductor",
                "sector": "Power Semiconductors",
                "lens_ids": ["ai_agent_compute", "semiconductors"],
                "metrics": {"valuation": 72, "quality": 58, "growth": 64, "revision": 61, "momentum": 55},
                "evidence": ["AI data-center revenue doubled year over year"],
                "gaps": ["Confirm normalized PER after next earnings"],
            }
        ],
    }

    parsed = parse_dashboard_input(payload)

    assert isinstance(parsed, DashboardInput)
    assert parsed.lenses[0].kind == LensKind.THESIS
    assert parsed.lenses[1].kind == LensKind.SECTOR
    assert parsed.stocks[0].lens_ids == ["ai_agent_compute", "semiconductors"]
    assert CandidateStatus.WATCH.value == "Watch"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_dashboard_models.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'dashboard'`.

- [ ] **Step 3: Create package exports**

Create `dashboard/__init__.py`:

```python
"""Lens-first personal investment dashboard."""
```

- [ ] **Step 4: Implement dashboard models**

Create `dashboard/models.py`:

```python
"""Domain models for the lens investment dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class LensKind(str, Enum):
    THESIS = "thesis"
    SECTOR = "sector"
    MACRO = "macro"
    FACTOR = "factor"


class CandidateStatus(str, Enum):
    WATCH = "Watch"
    RESEARCH = "Research"
    SETUP = "Setup"
    AVOID = "Avoid"
    BLOCKED = "Blocked"
    DROPPED = "Dropped"


@dataclass(frozen=True)
class MarketRegime:
    verdict: str
    risk_appetite: str
    rates: str
    dollar: str
    volatility: str
    notes: list[str]


@dataclass(frozen=True)
class Lens:
    id: str
    kind: LensKind
    name: str
    conviction: str
    direction: str
    weights: dict[str, float]
    risks: list[str]


@dataclass(frozen=True)
class StockMetrics:
    valuation: float
    quality: float
    growth: float
    revision: float
    momentum: float


@dataclass(frozen=True)
class StockInput:
    ticker: str
    company: str
    sector: str
    lens_ids: list[str]
    metrics: StockMetrics
    evidence: list[str]
    gaps: list[str]
    blocked: bool = False


@dataclass(frozen=True)
class DashboardInput:
    as_of: str
    regime: MarketRegime
    lenses: list[Lens]
    stocks: list[StockInput]


@dataclass(frozen=True)
class Candidate:
    ticker: str
    company: str
    sector: str
    linked_lenses: list[Lens]
    score: float
    status: CandidateStatus
    strongest_lens: str
    evidence: list[str]
    gaps: list[str]
    risk_flags: list[str]


@dataclass(frozen=True)
class Dashboard:
    as_of: str
    regime: MarketRegime
    lenses: list[Lens]
    candidates: list[Candidate]


def parse_dashboard_input(payload: dict[str, Any]) -> DashboardInput:
    regime_payload = payload["regime"]
    lenses = [
        Lens(
            id=str(item["id"]),
            kind=LensKind(str(item["kind"])),
            name=str(item["name"]),
            conviction=str(item["conviction"]),
            direction=str(item["direction"]),
            weights={str(key): float(value) for key, value in item.get("weights", {}).items()},
            risks=[str(value) for value in item.get("risks", [])],
        )
        for item in payload.get("lenses", [])
    ]
    stocks = [
        StockInput(
            ticker=str(item["ticker"]),
            company=str(item["company"]),
            sector=str(item["sector"]),
            lens_ids=[str(value) for value in item.get("lens_ids", [])],
            metrics=_parse_metrics(item.get("metrics", {})),
            evidence=[str(value) for value in item.get("evidence", [])],
            gaps=[str(value) for value in item.get("gaps", [])],
            blocked=bool(item.get("blocked", False)),
        )
        for item in payload.get("stocks", [])
    ]
    return DashboardInput(
        as_of=str(payload["as_of"]),
        regime=MarketRegime(
            verdict=str(regime_payload["verdict"]),
            risk_appetite=str(regime_payload["risk_appetite"]),
            rates=str(regime_payload["rates"]),
            dollar=str(regime_payload["dollar"]),
            volatility=str(regime_payload["volatility"]),
            notes=[str(value) for value in regime_payload.get("notes", [])],
        ),
        lenses=lenses,
        stocks=stocks,
    )


def _parse_metrics(payload: dict[str, Any]) -> StockMetrics:
    return StockMetrics(
        valuation=float(payload.get("valuation", 0)),
        quality=float(payload.get("quality", 0)),
        growth=float(payload.get("growth", 0)),
        revision=float(payload.get("revision", 0)),
        momentum=float(payload.get("momentum", 0)),
    )
```

- [ ] **Step 5: Include package in build config**

Modify `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["data", "utils", "signals", "dashboard"]
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_dashboard_models.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add dashboard/__init__.py dashboard/models.py tests/test_dashboard_models.py pyproject.toml
git commit -m "feat: add dashboard domain models"
```

---

### Task 2: Lens Screener And Candidate Status

**Files:**
- Create: `dashboard/screeners.py`
- Test: `tests/test_dashboard_screeners.py`

- [ ] **Step 1: Write failing screener tests**

Create `tests/test_dashboard_screeners.py`:

```python
from dashboard.models import CandidateStatus, parse_dashboard_input
from dashboard.screeners import build_dashboard


def test_candidate_priority_comes_from_lens_overlap_and_weighted_score():
    parsed = parse_dashboard_input(
        {
            "as_of": "2026-05-29",
            "regime": {
                "verdict": "pass",
                "risk_appetite": "risk-on",
                "rates": "down",
                "dollar": "stable",
                "volatility": "low",
                "notes": [],
            },
            "lenses": [
                {"id": "ai_power", "kind": "thesis", "name": "AI power bottleneck", "conviction": "high", "direction": "improving", "weights": {"growth": 0.30, "revision": 0.25, "valuation": 0.20, "momentum": 0.15, "quality": 0.10}, "risks": []},
                {"id": "power_semis", "kind": "sector", "name": "Power Semis", "conviction": "medium", "direction": "stable", "weights": {"valuation": 0.30, "growth": 0.20, "revision": 0.20, "momentum": 0.15, "quality": 0.15}, "risks": []},
                {"id": "low_per_revision", "kind": "factor", "name": "Low PER + revision", "conviction": "medium", "direction": "improving", "weights": {"valuation": 0.40, "revision": 0.30, "quality": 0.15, "growth": 0.10, "momentum": 0.05}, "risks": []},
            ],
            "stocks": [
                {"ticker": "ON", "company": "ON Semiconductor", "sector": "Power Semis", "lens_ids": ["ai_power", "power_semis", "low_per_revision"], "metrics": {"valuation": 76, "quality": 60, "growth": 68, "revision": 72, "momentum": 61}, "evidence": ["AI data-center business growing"], "gaps": []},
                {"ticker": "EXPENSIVE", "company": "Expensive Compute", "sector": "Semis", "lens_ids": ["ai_power"], "metrics": {"valuation": 22, "quality": 80, "growth": 88, "revision": 82, "momentum": 85}, "evidence": ["Strong growth"], "gaps": []},
            ],
        }
    )

    dashboard = build_dashboard(parsed)

    assert dashboard.candidates[0].ticker == "ON"
    assert dashboard.candidates[0].status == CandidateStatus.SETUP
    assert dashboard.candidates[0].strongest_lens == "AI power bottleneck"
    assert dashboard.candidates[1].status == CandidateStatus.WATCH


def test_blocked_and_missing_evidence_control_status():
    parsed = parse_dashboard_input(
        {
            "as_of": "2026-05-29",
            "regime": {"verdict": "conditional", "risk_appetite": "neutral", "rates": "stable", "dollar": "stable", "volatility": "normal", "notes": []},
            "lenses": [
                {"id": "semis", "kind": "sector", "name": "Semiconductors", "conviction": "medium", "direction": "stable", "weights": {"valuation": 0.25, "quality": 0.25, "growth": 0.20, "revision": 0.20, "momentum": 0.10}, "risks": []}
            ],
            "stocks": [
                {"ticker": "KRX:005930", "company": "Samsung Electronics", "sector": "Semiconductors", "lens_ids": ["semis"], "metrics": {"valuation": 70, "quality": 70, "growth": 55, "revision": 50, "momentum": 45}, "evidence": ["Memory cycle recovery"], "gaps": [], "blocked": True},
                {"ticker": "GAP", "company": "Gap Candidate", "sector": "Semiconductors", "lens_ids": ["semis"], "metrics": {"valuation": 80, "quality": 60, "growth": 60, "revision": 60, "momentum": 60}, "evidence": [], "gaps": ["source access gap"]},
            ],
        }
    )

    dashboard = build_dashboard(parsed)

    statuses = {candidate.ticker: candidate.status for candidate in dashboard.candidates}
    assert statuses["KRX:005930"] == CandidateStatus.BLOCKED
    assert statuses["GAP"] == CandidateStatus.RESEARCH
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_dashboard_screeners.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'dashboard.screeners'`.

- [ ] **Step 3: Implement deterministic screener**

Create `dashboard/screeners.py`:

```python
"""Scoring and candidate status logic for the lens dashboard."""

from __future__ import annotations

from dashboard.models import Candidate, CandidateStatus, Dashboard, DashboardInput, Lens, StockInput, StockMetrics


METRIC_NAMES = ("valuation", "quality", "growth", "revision", "momentum")


def build_dashboard(source: DashboardInput) -> Dashboard:
    lens_by_id = {lens.id: lens for lens in source.lenses}
    candidates = [_build_candidate(stock, lens_by_id) for stock in source.stocks]
    candidates.sort(key=lambda item: (item.status != CandidateStatus.SETUP, -len(item.linked_lenses), -item.score, item.ticker))
    return Dashboard(
        as_of=source.as_of,
        regime=source.regime,
        lenses=source.lenses,
        candidates=candidates,
    )


def _build_candidate(stock: StockInput, lens_by_id: dict[str, Lens]) -> Candidate:
    linked = [lens_by_id[lens_id] for lens_id in stock.lens_ids if lens_id in lens_by_id]
    lens_scores = [(lens, _score_for_lens(stock.metrics, lens)) for lens in linked]
    score = round(sum(score for _, score in lens_scores) / len(lens_scores), 1) if lens_scores else 0.0
    strongest = max(lens_scores, key=lambda item: item[1])[0].name if lens_scores else "-"
    risk_flags = _risk_flags(stock, score)
    return Candidate(
        ticker=stock.ticker,
        company=stock.company,
        sector=stock.sector,
        linked_lenses=linked,
        score=score,
        status=_status_for(stock, linked, score),
        strongest_lens=strongest,
        evidence=stock.evidence,
        gaps=stock.gaps,
        risk_flags=risk_flags,
    )


def _score_for_lens(metrics: StockMetrics, lens: Lens) -> float:
    weighted_sum = 0.0
    total_weight = 0.0
    for metric in METRIC_NAMES:
        weight = float(lens.weights.get(metric, 0.0))
        weighted_sum += getattr(metrics, metric) * weight
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return weighted_sum / total_weight


def _status_for(stock: StockInput, linked: list[Lens], score: float) -> CandidateStatus:
    if stock.blocked:
        return CandidateStatus.BLOCKED
    if not stock.evidence or stock.gaps:
        return CandidateStatus.RESEARCH
    if len(linked) >= 2 and score >= 65:
        return CandidateStatus.SETUP
    if score < 35:
        return CandidateStatus.AVOID
    return CandidateStatus.WATCH


def _risk_flags(stock: StockInput, score: float) -> list[str]:
    flags: list[str] = []
    if stock.metrics.valuation < 35:
        flags.append("valuation stretch")
    if stock.metrics.revision < 40:
        flags.append("weak revision")
    if score < 35:
        flags.append("low composite score")
    if stock.gaps:
        flags.append("evidence gap")
    return flags
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_dashboard_screeners.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add dashboard/screeners.py tests/test_dashboard_screeners.py
git commit -m "feat: score lens dashboard candidates"
```

---

### Task 3: Sample Data Loader

**Files:**
- Create: `dashboard/sample_data.py`
- Test: `tests/test_dashboard_models.py`

- [ ] **Step 1: Add failing sample-data test**

Append to `tests/test_dashboard_models.py`:

```python
from dashboard.sample_data import load_sample_dashboard_input


def test_sample_dashboard_input_contains_initial_lens_set():
    parsed = load_sample_dashboard_input()

    lens_ids = {lens.id for lens in parsed.lenses}
    assert {"ai_agent_compute", "ai_power_bottleneck", "low_per_revision", "semiconductors", "power_analog"}.issubset(lens_ids)
    assert any(stock.ticker == "ON" for stock in parsed.stocks)
    assert any(stock.ticker == "TXN" for stock in parsed.stocks)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_dashboard_models.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'dashboard.sample_data'`.

- [ ] **Step 3: Implement embedded sample data**

Create `dashboard/sample_data.py`:

```python
"""Curated v1 seed data for local dashboard rendering."""

from __future__ import annotations

from dashboard.models import DashboardInput, parse_dashboard_input


SAMPLE_DASHBOARD = {
    "as_of": "2026-05-29",
    "regime": {
        "verdict": "conditional",
        "risk_appetite": "risk-on",
        "rates": "stable",
        "dollar": "stable",
        "volatility": "low",
        "notes": [
            "AI infrastructure demand appears real, but semiconductor valuations can still correct.",
            "Power and analog semis may be a second-order AI infrastructure bottleneck.",
        ],
    },
    "lenses": [
        {"id": "ai_agent_compute", "kind": "thesis", "name": "AI agent compute", "conviction": "high", "direction": "improving", "weights": {"growth": 0.35, "revision": 0.25, "valuation": 0.15, "momentum": 0.15, "quality": 0.10}, "risks": ["capex fatigue"]},
        {"id": "ai_power_bottleneck", "kind": "thesis", "name": "AI power bottleneck", "conviction": "high", "direction": "improving", "weights": {"growth": 0.25, "revision": 0.25, "valuation": 0.20, "quality": 0.15, "momentum": 0.15}, "risks": ["late-cycle price hikes"]},
        {"id": "low_per_revision", "kind": "factor", "name": "Low PER + earnings revision", "conviction": "medium", "direction": "improving", "weights": {"valuation": 0.40, "revision": 0.30, "quality": 0.15, "growth": 0.10, "momentum": 0.05}, "risks": ["value trap"]},
        {"id": "semiconductors", "kind": "sector", "name": "Semiconductors", "conviction": "medium", "direction": "stable", "weights": {"growth": 0.25, "revision": 0.20, "valuation": 0.25, "momentum": 0.20, "quality": 0.10}, "risks": ["valuation stretch"]},
        {"id": "power_analog", "kind": "sector", "name": "Power and analog semis", "conviction": "medium", "direction": "improving", "weights": {"valuation": 0.25, "quality": 0.20, "growth": 0.20, "revision": 0.20, "momentum": 0.15}, "risks": ["auto and industrial cycle drag"]},
        {"id": "risk_on_liquidity", "kind": "macro", "name": "Risk-on liquidity", "conviction": "medium", "direction": "stable", "weights": {"momentum": 0.35, "growth": 0.25, "revision": 0.20, "quality": 0.10, "valuation": 0.10}, "risks": ["liquidity reversal"]},
    ],
    "stocks": [
        {"ticker": "ON", "company": "ON Semiconductor", "sector": "Power Semiconductors", "lens_ids": ["ai_power_bottleneck", "power_analog", "low_per_revision"], "metrics": {"valuation": 74, "quality": 58, "growth": 66, "revision": 70, "momentum": 60}, "evidence": ["AI data-center business reported strong growth"], "gaps": ["Confirm normalized earnings after next filing"]},
        {"ticker": "TXN", "company": "Texas Instruments", "sector": "Analog Semiconductors", "lens_ids": ["ai_power_bottleneck", "power_analog"], "metrics": {"valuation": 48, "quality": 78, "growth": 58, "revision": 62, "momentum": 68}, "evidence": ["Industrial and data-center demand commentary supports power-management exposure"], "gaps": []},
        {"ticker": "ADI", "company": "Analog Devices", "sector": "Analog Semiconductors", "lens_ids": ["ai_power_bottleneck", "power_analog"], "metrics": {"valuation": 42, "quality": 82, "growth": 62, "revision": 64, "momentum": 70}, "evidence": ["Power-density positioning strengthened by Empower acquisition"], "gaps": []},
        {"ticker": "NVDA", "company": "NVIDIA", "sector": "Accelerated Compute", "lens_ids": ["ai_agent_compute", "semiconductors", "risk_on_liquidity"], "metrics": {"valuation": 30, "quality": 92, "growth": 95, "revision": 88, "momentum": 90}, "evidence": ["Data-center revenue remains the primary AI infrastructure signal"], "gaps": ["Valuation already reflects large option value"]},
    ],
}


def load_sample_dashboard_input() -> DashboardInput:
    return parse_dashboard_input(SAMPLE_DASHBOARD)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run pytest tests/test_dashboard_models.py tests/test_dashboard_screeners.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add dashboard/sample_data.py tests/test_dashboard_models.py
git commit -m "feat: add sample lens dashboard data"
```

---

### Task 4: HTML And Markdown Rendering

**Files:**
- Create: `dashboard/render.py`
- Test: `tests/test_dashboard_render.py`

- [ ] **Step 1: Write failing render tests**

Create `tests/test_dashboard_render.py`:

```python
from dashboard.render import render_dashboard_html, render_dashboard_markdown
from dashboard.sample_data import load_sample_dashboard_input
from dashboard.screeners import build_dashboard


def test_render_dashboard_html_contains_core_sections_and_no_raw_json():
    dashboard = build_dashboard(load_sample_dashboard_input())

    html = render_dashboard_html(dashboard)

    assert "<!doctype html>" in html
    assert "Lens Investment Dashboard" in html
    assert "시장 국면" in html
    assert "렌즈 맵" in html
    assert "렌즈 중첩 후보" in html
    assert "ON Semiconductor" in html
    assert "raw JSON" not in html
    assert "data-asset-purpose" not in html


def test_render_dashboard_markdown_is_compact_briefing():
    dashboard = build_dashboard(load_sample_dashboard_input())

    text = render_dashboard_markdown(dashboard)

    assert text.startswith("# Lens Investment Dashboard")
    assert "## 시장 국면" in text
    assert "## 상위 후보" in text
    assert "ON" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_dashboard_render.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'dashboard.render'`.

- [ ] **Step 3: Implement renderer**

Create `dashboard/render.py`:

```python
"""Render lens dashboard outputs."""

from __future__ import annotations

from html import escape

from dashboard.models import Candidate, Dashboard


def render_dashboard_markdown(dashboard: Dashboard) -> str:
    lines = [
        "# Lens Investment Dashboard",
        "",
        f"기준일: {dashboard.as_of}",
        "",
        "## 시장 국면",
        f"- verdict: {dashboard.regime.verdict}",
        f"- risk appetite: {dashboard.regime.risk_appetite}",
        f"- rates: {dashboard.regime.rates}",
        f"- dollar: {dashboard.regime.dollar}",
        f"- volatility: {dashboard.regime.volatility}",
        "",
        "## 상위 후보",
    ]
    for candidate in dashboard.candidates[:10]:
        lens_names = ", ".join(lens.name for lens in candidate.linked_lenses)
        lines.append(
            f"- {candidate.ticker} {candidate.company}: {candidate.status.value}, score {candidate.score:.1f}, lenses {lens_names}"
        )
    return "\n".join(lines) + "\n"


def render_dashboard_html(dashboard: Dashboard) -> str:
    candidate_rows = "\n".join(_candidate_row(candidate) for candidate in dashboard.candidates)
    lens_cards = "\n".join(
        f"<article><h3>{escape(lens.name)}</h3><p>{escape(lens.kind.value)} · {escape(lens.conviction)} · {escape(lens.direction)}</p><p>{escape(', '.join(lens.risks) or '-')}</p></article>"
        for lens in dashboard.lenses
    )
    notes = "\n".join(f"<li>{escape(note)}</li>" for note in dashboard.regime.notes)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lens Investment Dashboard</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --ink: #111827;
      --muted: #5b6472;
      --line: #d9dee7;
      --panel: #ffffff;
      --accent: #0f766e;
      --warn: #b45309;
      --bad: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }}
    header {{ border-bottom: 1px solid var(--line); padding-bottom: 18px; margin-bottom: 24px; }}
    h1 {{ font-size: 30px; margin: 0 0 8px; letter-spacing: 0; }}
    h2 {{ font-size: 20px; margin: 28px 0 12px; letter-spacing: 0; }}
    h3 {{ font-size: 15px; margin: 0 0 4px; letter-spacing: 0; }}
    .muted {{ color: var(--muted); }}
    .kpis {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }}
    .kpi, article {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
    .kpi strong {{ display: block; font-size: 18px; }}
    .lens-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); }}
    th, td {{ padding: 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 13px; }}
    .status-Setup {{ color: var(--accent); font-weight: 700; }}
    .status-Research {{ color: var(--warn); font-weight: 700; }}
    .status-Blocked, .status-Avoid {{ color: var(--bad); font-weight: 700; }}
    @media (max-width: 760px) {{
      main {{ padding: 18px 12px 36px; }}
      .kpis {{ grid-template-columns: 1fr 1fr; }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <p class="muted">기준일 {escape(dashboard.as_of)}</p>
    <h1>Lens Investment Dashboard</h1>
    <p>Thesis, sector, macro, factor lens가 같은 후보를 가리키는지 점검합니다.</p>
  </header>
  <section>
    <h2>시장 국면</h2>
    <div class="kpis">
      <div class="kpi"><span>Verdict</span><strong>{escape(dashboard.regime.verdict)}</strong></div>
      <div class="kpi"><span>Risk</span><strong>{escape(dashboard.regime.risk_appetite)}</strong></div>
      <div class="kpi"><span>Rates</span><strong>{escape(dashboard.regime.rates)}</strong></div>
      <div class="kpi"><span>Dollar</span><strong>{escape(dashboard.regime.dollar)}</strong></div>
      <div class="kpi"><span>Volatility</span><strong>{escape(dashboard.regime.volatility)}</strong></div>
    </div>
    <ul>{notes}</ul>
  </section>
  <section>
    <h2>렌즈 맵</h2>
    <div class="lens-grid">{lens_cards}</div>
  </section>
  <section>
    <h2>렌즈 중첩 후보</h2>
    <table>
      <thead><tr><th>종목</th><th>상태</th><th>점수</th><th>렌즈</th><th>강한 렌즈</th><th>Gap</th></tr></thead>
      <tbody>{candidate_rows}</tbody>
    </table>
  </section>
</main>
</body>
</html>
"""


def _candidate_row(candidate: Candidate) -> str:
    lens_names = ", ".join(lens.name for lens in candidate.linked_lenses)
    gaps = "; ".join(candidate.gaps) or "-"
    return (
        "<tr>"
        f"<td><strong>{escape(candidate.ticker)}</strong><br>{escape(candidate.company)}<br><span class=\"muted\">{escape(candidate.sector)}</span></td>"
        f"<td class=\"status-{escape(candidate.status.value)}\">{escape(candidate.status.value)}</td>"
        f"<td>{candidate.score:.1f}</td>"
        f"<td>{escape(lens_names)}</td>"
        f"<td>{escape(candidate.strongest_lens)}</td>"
        f"<td>{escape(gaps)}</td>"
        "</tr>"
    )
```

- [ ] **Step 4: Run render tests to verify pass**

Run:

```bash
uv run pytest tests/test_dashboard_render.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add dashboard/render.py tests/test_dashboard_render.py
git commit -m "feat: render lens dashboard reports"
```

---

### Task 5: CLI Report Writer

**Files:**
- Create: `scripts/render_lens_dashboard.py`
- Test: `tests/test_dashboard_render.py`

- [ ] **Step 1: Add failing CLI writer test**

Append to `tests/test_dashboard_render.py`:

```python
from pathlib import Path

from scripts.render_lens_dashboard import write_dashboard_reports


def test_write_dashboard_reports_creates_html_and_markdown(tmp_path):
    html_path, md_path = write_dashboard_reports(output_dir=tmp_path)

    assert html_path == tmp_path / "2026-05-29-lens-dashboard.html"
    assert md_path == tmp_path / "2026-05-29-lens-dashboard.md"
    assert "Lens Investment Dashboard" in html_path.read_text(encoding="utf-8")
    assert "## 상위 후보" in md_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_dashboard_render.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'scripts.render_lens_dashboard'`.

- [ ] **Step 3: Implement CLI writer**

Create `scripts/render_lens_dashboard.py`:

```python
"""Render the v1 lens investment dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path

from dashboard.render import render_dashboard_html, render_dashboard_markdown
from dashboard.sample_data import load_sample_dashboard_input
from dashboard.screeners import build_dashboard


DEFAULT_OUTPUT_DIR = Path("state/dashboard/reports")


def write_dashboard_reports(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    dashboard = build_dashboard(load_sample_dashboard_input())
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    html_path = target / f"{dashboard.as_of}-lens-dashboard.html"
    md_path = target / f"{dashboard.as_of}-lens-dashboard.md"
    html_path.write_text(render_dashboard_html(dashboard), encoding="utf-8")
    md_path.write_text(render_dashboard_markdown(dashboard), encoding="utf-8")
    return html_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the lens investment dashboard.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for HTML and Markdown reports.")
    args = parser.parse_args()
    html_path, md_path = write_dashboard_reports(args.output_dir)
    print(f"HTML: {html_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run CLI tests to verify pass**

Run:

```bash
uv run pytest tests/test_dashboard_render.py -q
```

Expected: pass.

- [ ] **Step 5: Run CLI manually**

Run:

```bash
uv run python scripts/render_lens_dashboard.py
```

Expected:

```text
HTML: state/dashboard/reports/2026-05-29-lens-dashboard.html
Markdown: state/dashboard/reports/2026-05-29-lens-dashboard.md
```

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/render_lens_dashboard.py tests/test_dashboard_render.py state/dashboard/reports/2026-05-29-lens-dashboard.html state/dashboard/reports/2026-05-29-lens-dashboard.md
git commit -m "feat: add lens dashboard report command"
```

---

### Task 6: Documentation And Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document dashboard command**

Add this section to `README.md` after the TradingView signal console section:

```markdown
## Lens Investment Dashboard

렌즈 투자 대시보드는 thesis, sector, macro, factor를 같은 계층의 Lens로 두고, 여러 렌즈가 동시에 가리키는 후보 종목을 점검합니다.

```bash
uv run python scripts/render_lens_dashboard.py
```

출력:

```text
state/dashboard/reports/YYYY-MM-DD-lens-dashboard.html
state/dashboard/reports/YYYY-MM-DD-lens-dashboard.md
```

v1은 curated sample data로 모델과 화면을 검증합니다. live valuation/news API, raw source intake, Telegram delivery는 후속 단계에서 같은 `dashboard` 모델 위에 붙입니다.
```

- [ ] **Step 2: Run focused dashboard tests**

Run:

```bash
uv run pytest tests/test_dashboard_models.py tests/test_dashboard_screeners.py tests/test_dashboard_render.py -q
```

Expected: pass.

- [ ] **Step 3: Run full project tests**

Run:

```bash
uv run pytest -q
```

Expected: pass.

- [ ] **Step 4: Inspect generated HTML manually**

Run:

```bash
open state/dashboard/reports/2026-05-29-lens-dashboard.html
```

Expected: browser opens the dashboard. Confirm first viewport shows verdict, regime KPIs, and no text overlap at desktop width.

- [ ] **Step 5: Commit docs and verification**

Run:

```bash
git add README.md
git commit -m "docs: document lens investment dashboard"
```

---

## Self-Review

- Spec coverage: The plan implements Market Regime, same-level Lens types, Universe through curated stock inputs, Screener scoring, Candidate statuses, Action-oriented Markdown/HTML output, evidence and gaps, and v1 HTML dashboard output.
- Scope control: Live data APIs, raw source ingestion, Telegram delivery, and portfolio accounting remain outside v1. This keeps the first implementation testable and useful.
- Placeholder scan: No TBD, TODO, "similar to", or unspecified error handling remains.
- Type consistency: `DashboardInput`, `Lens`, `StockInput`, `Candidate`, and `Dashboard` are defined before use. Renderer and CLI consume `Dashboard` from `build_dashboard`.
- Verification: Focused tests, full `uv run pytest -q`, and manual HTML inspection are included.
