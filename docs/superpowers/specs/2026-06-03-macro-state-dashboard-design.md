# Macro State Dashboard Design

## Verdict

04_stock_intel should extend the existing personal investment dashboard with a
macro state cockpit. The dashboard should not be a geopolitics dashboard.
Instead, it should show fixed market regime indicators and attach the current
dominant issue as a short, source-aware narrative card.

Recommended first version:

```text
Macro State -> Current Issue -> Indicator Reads -> Portfolio/Watchlist Impact
```

This keeps the project centered on stock intelligence while making market
conditions explicit before individual candidates are reviewed.

## Problem

The existing dashboard already has a market regime strip, but it is too narrow
for the user's current decision loop. Recent discussion showed a recurring need
to answer:

```text
Is the market actually pricing the dominant issue, or are equities ignoring
warnings already visible in oil, rates, dollar, breadth, or volatility?
```

Geopolitics may be the current issue, but the same structure should work for
Fed policy, CPI, AI capex, China, earnings, liquidity, or commodity shocks.

## Goals

- Show the market's current state before stock candidate review.
- Track fixed macro dimensions: breadth, sentiment, rates, FX, commodities,
  and oil.
- Show 1-3 current issue cards that explain what is driving the regime read.
- Compare the issue narrative against market indicators.
- Surface explicit next actions for watchlist behavior.
- Preserve data freshness, source gaps, and degraded sections.
- Keep the output mobile-readable and compatible with the existing HTML and
  Markdown dashboard flows.

## Non-Goals

- No geopolitical prediction engine.
- No automatic trading or portfolio rebalancing.
- No opaque LLM-only market score.
- No long news feed or raw article dump in the primary screen.
- No replacement of the existing lens/candidate dashboard.
- No hard buy/sell recommendation language.

## Screen Structure

### 1. Macro State Header

Purpose: give a verdict-first market read in the first viewport.

Required fields:

- current state: `risk-on`, `conditional`, `risk-off`, or `fragile rally`
- why it matters: one concise explanation linking indicators to equity risk
- next action: one workflow instruction such as `chase 제한`, `후보 압축`,
  `방어 전환 감시`, or `신규 진입 보류`
- generated timestamp and data freshness

Example:

```text
현재 상태: conditional / 지수는 강하지만 내부 체력과 비용 압력은 엇갈림
왜 중요한가: AI 주도 랠리가 breadth 약화, 유가, 금리 재상승을 아직 흡수하는 구간
다음 행동: Brent·10Y·SPY/RSP 동시 악화 시 신규 진입 강도 낮춤
```

### 2. Current Issue Cards

Purpose: show what market participants are responding to today.

Each card should include:

- theme: geopolitics, Fed, inflation, earnings, China, AI capex, liquidity,
  commodities, or custom
- issue state: active, easing, worsening, unresolved, source gap
- market read: whether indicators confirm, reject, or ignore the issue
- triggers to watch
- source summary and source access gaps

For the current geopolitics use case:

```text
주요 이슈: 지정학
현재 상태: 휴전 기대는 남아 있으나 당사자 구속력 약함
시장 해석: 주식은 AI 랠리로 방어, 유가와 금리는 종전 신뢰도를 의심
주의 트리거: Brent 95달러 위 고착, 10Y 4.5% 재상승, VIX 동반 상승
접근 갭: 헤즈볼라 묵시적 수용 여부, 이란 안보조직의 협상 제약
```

### 3. Indicator Grid

Purpose: make market confirmation or divergence visible.

Fixed dimensions:

- breadth: `SPY/RSP`, `QQQ/IWM`, `S5FI`, optional advance/decline line
- sentiment: `VIX`, optional put/call or fear/greed proxy
- rates: `^TNX`, optional `^IRX` or 2Y/10Y spread when available
- FX: `DXY`, `USDKRW`
- commodities: `GLD`, `CPER` or copper futures when available
- oil: `BZ=F` or `CL=F`

Each indicator read should show:

- current value
- latest change
- short read in Korean
- state label: supportive, warning, stressed, unavailable
- data source and freshness

The grid should avoid implying precision when a source is missing. Missing data
must be shown as an explicit gap, not silently omitted.

### 4. Market-To-Watchlist Impact

Purpose: translate the macro state into candidate handling.

Required outputs:

- growth/AI chase condition
- cyclicals condition
- energy/defense relative strength condition
- Korea market pressure from USDKRW and oil
- sectors requiring caution such as airlines, chemicals, consumer, and
  transport when oil/rates rise

This section should connect to existing candidate cards without changing their
independence or candidate status logic.

## Data Flow

The implementation should reuse the existing snapshot overlay model:

```text
providers -> snapshot cache -> live dashboard input -> screeners -> renderer
```

Add macro state data as a structured payload in the snapshot. The renderer
should consume prepared reads instead of doing source fetching in HTML
generation.

Suggested modules:

- `dashboard/providers/macro.py`: expand symbol coverage and raw quote loading
- `dashboard/macro_state.py`: derive state labels, issue confirmation, and
  watchlist impact
- `dashboard/models.py`: add optional macro state and issue card dataclasses
- `dashboard/render.py`: render header, issue cards, and indicator grid
- `tests/test_macro_state.py`: deterministic derivation tests

## Error Handling

- Provider failure should degrade only the affected indicator group.
- Snapshot absence should fall back to curated sample data with clear labeling.
- Issue cards may be manually curated when fresh news automation is not
  available.
- If the current issue has no reliable source, mark `source gap` and avoid
  confident causal claims.
- If breadth symbols are unavailable, show breadth as `확인 필요` rather than
  inferring from S&P alone.

## Testing

Use test-first implementation.

Required tests:

- Derives `fragile rally` when cap-weight equity is strong but breadth, rates,
  and oil are warning.
- Keeps issue card separate from fixed macro dimensions.
- Marks missing indicator data as an explicit gap.
- Renders Korean primary labels without raw implementation terms.
- Preserves existing dashboard rendering tests.

## Initial Scope

Version 1 should implement the macro state cockpit inside the existing
dashboard, not as a separate app.

Included:

- one macro state header
- one to three issue cards
- fixed indicator grid
- watchlist impact summary
- snapshot-backed data freshness

Deferred:

- automated news article ingestion
- LLM-generated daily issue summaries
- deep drilldown charts for every indicator
- Telegram command integration
- portfolio allocation logic

## Approval

The user approved the `Macro State First` design on 2026-06-03 after reviewing
the visual mockup direction.
