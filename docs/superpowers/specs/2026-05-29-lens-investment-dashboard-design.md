# Lens Investment Dashboard Design

## Verdict

04_stock_intel should add a personal investment dashboard built around a
same-level lens model:

```text
Market Regime -> Lens -> Universe -> Screener -> Candidate -> Action
```

Thesis, sector, macro, and factor are all lenses. A stock becomes more
interesting when multiple independent lenses point to it at the same time.

## Problem

The user has accumulated useful market insights across conversations:

- AI agents may structurally increase inference compute demand.
- AI infrastructure demand may spread from GPU and HBM into power, analog,
  cooling, networking, and electrical infrastructure.
- Low PER remains useful, but only when paired with earnings quality, revision,
  free cash flow, and cycle awareness.
- Macro regime shifts can make the same valuation signal either attractive or
  a trap.

Today these insights are not yet connected into a repeatable decision loop. The
project can fetch or format stock data, but it does not yet answer the higher
order question:

```text
Which market lenses currently agree on the same investable candidates?
```

## Goals

- Represent thesis, sector, macro, and factor as first-class lenses at the same
  layer.
- Connect each stock candidate to one or more lenses without forcing a strict
  thesis-first hierarchy.
- Screen each lens with weights that fit its purpose.
- Surface candidates by lens overlap, not by one raw score alone.
- Keep candidate states separate from buy recommendations.
- Preserve source evidence and explicit gaps for each candidate decision.
- Support both daily market checks and weekly thesis conviction updates.

## Non-Goals

- No automatic trading.
- No direct buy or sell recommendation language in v1.
- No attempt to replace the existing TradingView signal alert flow.
- No personal portfolio accounting in v1.
- No opaque LLM-only ranking without traceable numeric and source inputs.
- No raw news dump as the primary output.

## Conceptual Model

### Market Regime

Market regime is the context layer. It should describe the current environment
before individual stocks are ranked.

Example regime fields:

- risk appetite: risk-on, neutral, risk-off
- rates direction
- dollar direction
- VIX or volatility state
- liquidity condition
- sector breadth
- AI or semiconductor heat state

Regime does not own candidates directly. It changes lens weights and warning
thresholds.

### Lens

Lens is the main organizing layer. Lenses are peers, not parent and child
categories.

Required v1 lens types:

- thesis lens: AI agent compute, AI power bottleneck, stablecoin rails
- sector lens: semiconductors, power/analog, payments, financials, industrials
- macro lens: rates down, dollar down, liquidity expansion, risk-off defense
- factor lens: low PER, free cash flow yield, quality, earnings revision,
  momentum

The same stock may appear under several lenses:

```text
ON Semiconductor
-> sector lens: power semis
-> thesis lens: AI power bottleneck
-> factor lens: cyclical recovery / valuation reset
-> macro lens: manufacturing and rate-cycle sensitivity
```

### Universe

Universe is the set of stocks eligible for screening. v1 should support a
curated universe before broad market coverage.

Suggested initial universe:

- US AI infrastructure names
- US power and analog semiconductor names
- US low-PER or FCF-yield candidates connected to active theses
- Korea candidates already supported by existing 04_stock_intel data modules

The universe should be tagged, not duplicated. A single stock record can carry
many lens links.

### Screener

Screeners apply lens-specific scoring. The same raw data can receive different
weights under different lenses.

Baseline metrics:

- valuation: trailing PER, forward PER, normalized PER, EV/EBITDA, FCF yield
- quality: ROE, ROIC, gross margin, operating margin, leverage
- growth: revenue growth, EPS growth, backlog, AI/data-center exposure
- revision: EPS revision, guidance change, analyst estimate direction
- momentum: 3M relative strength, 6M relative strength, 52-week distance
- risk: valuation stretch, peak earnings risk, capex fatigue, customer
  concentration, cycle rollover
- evidence: source count, source recency, source reliability, unresolved gaps

Example weighting:

- AI agent compute thesis: growth, backlog, capex exposure, gross margin,
  data-center revenue
- AI power bottleneck thesis: power-density exposure, AI server design wins,
  margin expansion, lead time, backlog
- low PER factor: normalized PER, FCF yield, EPS revision, balance sheet,
  cycle position
- sector lens: peer-relative valuation, peer-relative growth, relative strength
- macro lens: rates sensitivity, dollar sensitivity, cyclicality, defensive
  quality

### Candidate

Candidate is the investable object after screening. Candidates must have a
status, not a recommendation.

Required statuses:

- Watch: thesis or sector fit exists, but price or evidence is not compelling
- Research: attractive signal exists, but required evidence is missing
- Setup: lens overlap and price/technical setup are improving
- Avoid: valuation, cycle, or thesis risk dominates
- Blocked: independence, compliance, source access, or safety restriction
- Dropped: previously tracked, but no longer meets the minimum evidence bar

### Action

Action is the dashboard output. It should be phrased as workflow guidance, not
investment advice.

Examples:

- add to watchlist
- refresh valuation and revision data
- inspect latest earnings call
- compare against sector peers
- wait for pullback
- remove from active candidates
- mark source gap
- manual independence check required

## Dashboard Views

### 1. Regime Header

Purpose: make the current market backdrop visible before stock selection.

Required fields:

- overall regime verdict
- key macro changes
- sector heat map summary
- volatility state
- risk flags
- data freshness timestamp

### 2. Lens Map

Purpose: show which thesis, sector, macro, and factor lenses are active.

Each lens should show:

- conviction: high, medium, low
- direction: improving, stable, weakening
- linked universe count
- top candidates
- top risks
- last updated date

### 3. Lens Overlap Board

Purpose: identify stocks selected by multiple independent lenses.

Required columns:

- ticker
- company
- linked lenses
- overlap count
- strongest lens
- valuation signal
- revision signal
- momentum signal
- risk flag
- candidate status

### 4. Sector / Peer Screener

Purpose: inspect a sector lens without assuming a thesis hierarchy.

Required columns:

- ticker
- sector
- industry or value-chain role
- PER / forward PER
- FCF yield
- revenue growth
- gross margin direction
- EPS revision
- relative strength
- status

### 5. Candidate Detail

Purpose: explain why a candidate is on the board.

Required sections:

- verdict
- linked lenses
- bull case
- bear case
- required evidence
- recommended next action
- source references
- unresolved gaps

## Data Flow

```text
raw source / market data / manual note
-> source normalization
-> insight extraction
-> lens impact classification
-> universe tagging
-> lens-specific screening
-> candidate status update
-> dashboard rendering
-> Telegram or Markdown summary
```

The durable output should preserve the distinction between raw input, extracted
insight, candidate judgment, and user-facing rendering.

## Module Responsibility Mapping

Existing responsibilities remain:

- `data/`: source-specific data retrieval and graceful fallback
- `signals/`: TradingView and signal-related pipeline
- `utils/formatter.py`: Telegram formatting

New responsibilities likely needed:

- `dashboard/lenses.py`: lens definitions, types, and static metadata
- `dashboard/universe.py`: curated stock universe and lens tags
- `dashboard/screeners.py`: deterministic scoring functions
- `dashboard/candidates.py`: candidate status transitions and evidence gaps
- `dashboard/render.py`: dashboard and briefing rendering
- `dashboard/sources.py`: normalized source records for manual and automated raw
  inputs

These names are provisional for implementation planning. The important boundary
is that data fetching, scoring, candidate judgment, and rendering remain
separate.

## Storage

v1 can use local files before a database migration.

Suggested durable files:

- `state/dashboard/lenses.json`
- `state/dashboard/universe.json`
- `state/dashboard/candidates.json`
- `state/dashboard/sources/*.json`
- `state/dashboard/reports/YYYY-MM-DD.md`
- `state/dashboard/reports/YYYY-MM-DD.html`

If candidate history, score history, and source lineage become central, move to
SQLite with explicit migrations.

## Evidence And Gap Classification

Each candidate must separate:

- required evidence: missing data that blocks a useful status
- recommended evidence: data that would improve conviction
- source access gap: paywall, missing transcript, unavailable filing, failed API
- stale data gap: source exists but is too old
- model judgment gap: LLM-inferred link that needs human or source confirmation

No candidate should be promoted to Setup from LLM commentary alone.

## Initial Lens Set

v1 should start small:

- AI agent compute
- AI power bottleneck
- low PER plus earnings revision
- semiconductors
- power and analog semis
- risk-on liquidity
- risk-off defense

This is enough to test the model without creating a taxonomy project.

## Verification

Design-level verification before implementation:

- A sample stock can link to multiple lens types.
- A sector lens can discover a candidate before any thesis lens claims it.
- A thesis lens can discover cross-sector candidates.
- Low PER cannot pass without normalized earnings or revision checks.
- Candidate status can degrade when evidence becomes stale or a thesis weakens.
- Rendering can explain why the candidate is shown without exposing raw JSON as
  the primary user-facing view.

Implementation verification will be defined in the follow-up plan.

## Open Questions

- Whether v1 should output HTML first, Telegram first, or Markdown first.
- Whether US-only should launch first, with Korea added after the model proves
  useful.
- Which source APIs are reliable enough for valuation and revision data.
- Whether manual raw notes should enter through the existing vault raw-capture
  workflow or a project-local source intake command.
