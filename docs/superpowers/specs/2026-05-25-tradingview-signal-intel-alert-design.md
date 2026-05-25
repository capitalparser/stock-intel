# TradingView Signal Intel Alert Design

## Verdict

04_stock_intel becomes the canonical user-facing project for TradingView-driven buy-signal alerts with independence checks.

02_audit_safe_signals is no longer the product owner. It is a source of reusable webhook parsing, filter, dedup, and storage ideas. 03_tradingview_companion remains a separate pull-based chart analysis companion.

## Problem

The user already collects market ideas, important names, and watchlists in TradingView. A subscribed private TradingView indicator emits buy-oriented signals such as entry, breakout, pullback, and momentum buy. The user needs Telegram alerts when those signals fire, but the alert must also answer the audit-independence question first: is this a stock the user should not buy because of an auditor relationship such as Samjong/KPMG?

The project must not silently hide blocked signals. The blocked state is itself important information.

## Goals

- Receive TradingView private-indicator webhook payloads using the v6.2 JSON contract.
- Filter for buy-oriented signals only in the MVP.
- Classify the symbol market as Korea, US, Japan, or unknown.
- Run an independence decision before presenting any buy alert.
- Send Telegram messages for all material outcomes:
  - blocked independence
  - manual verification needed
  - no configured independence block found
- Reuse 04_stock_intel's existing Korean stock data modules for enrichment where they are reliable.
- Preserve raw signal payloads for later `/feed` and debugging.
- Document the TradingView CLI watchlist path as an operating helper.

## Non-Goals

- No automatic trade execution.
- No silent buy recommendation. Messages describe signal state and independence status.
- No automatic US/Japan auditor lookup in v1.
- No attempt to inspect private-indicator internals. The webhook JSON is the contract.
- No merge of 03_tradingview_companion into 04.
- No position lifecycle engine for sell, invalidation, or take-profit signals in v1.

## Product Boundary

### 04_stock_intel

Owns the Telegram experience and the alert pipeline:

```text
TradingView webhook
-> 04 webhook endpoint
-> v6.2 payload validation
-> buy-signal filter
-> dedup
-> market classification
-> independence decision
-> optional enrichment
-> Telegram alert
-> signal storage
```

### 02_audit_safe_signals

Becomes an implementation donor and eventual archive/compatibility surface. The reusable parts are:

- v6.1 Pydantic payload model
- buy filter
- dedup store
- `/signals` read endpoint idea
- SQLite webhook store

### 03_tradingview_companion

Keeps pull-path chart analysis:

- "look at this chart"
- "analyze my watchlist"
- TradingView Desktop/MCP chart reading
- screenshots or visual context in later integrations

## TradingView Private Indicator Feasibility

The provided `Webhook_참고자료_v6_2.md` is sufficient for implementation. The private indicator does not need to expose source code. The server only needs the alert payload.

TradingView webhook alerts can POST JSON if the alert message is valid JSON. Pine alert messages can use placeholders or script-generated JSON strings. Therefore the integration works when the user's alert message is the v6.2 JSON template supplied by the indicator author.

Implementation implication:

- The v6.2 payload becomes the canonical inbound schema.
- If a live alert omits a field, the server should reject or degrade based on whether the field is required for safety.
- Private indicator values not included in the JSON are not available to the server.

## v6.2 Payload Contract

The inbound model accepts the v6.2 38-field payload. Compared with the current 02 v6.1 model, v6.2 adds:

- `sb_z_score: float`

The model keeps compatibility with v6.1 by defaulting `sb_z_score` to `0.0` only for older fixtures. Live v6.2 alerts should include it.

Important fields:

- identity: `ticker`, `name`, `exchange`, `timeframe`
- signal: `action`, `type`, `desc`, `signal`, `conviction`
- price/risk: `price`, `sl`, `rr`
- quality: `score`, `status`, `market`, `daily_*`
- heat: `energy`, `atr_multiple`, `atr_dot`, `atr_dot_threshold`, `sb_z_score`, `rsi2`, `upper_wick_pct`

## Buy-Signal Scope

MVP sends primary buy alerts for `action == "BUY"` and these base types:

- `💰 정석 진입`
- `🚀 돌파 진입`
- `⚡ 공격 진입`
- `🔼 피라미딩 추매`
- `📈 모멘텀 BUY`
- `PEG Pullback`
- `PEG Rebreak`

The parser strips ` @SR↩` before matching. It should prefer semantic matching over exact emoji matching where possible because v6.2 changed some label emoji.

MVP does not send sell/check lifecycle alerts, except that the raw payload should be stored for future position-follow-up support.

## Independence Decision

### States

- `BLOCKED`: known blocked auditor match.
- `CLEAR`: Korean auditor data exists and no configured block matched.
- `MANUAL_VERIFY`: auditor data is unavailable or the market is not yet automatically supported.
- `UNKNOWN_MARKET`: market classification failed.

### Korean Stocks

Use existing `data/audit_firm.py` and `kreports` history.

Blocked auditor aliases include at least:

- `삼정회계법인`
- `삼정KPMG`
- `삼정 KPMG`
- `KPMG삼정`

The decision checks normalized current auditor first. If only recent history is available and the current year is stale, the message must say verification is needed.

### US And Japan

US and Japan alerts are accepted in v1, but automatic auditor lookup is not implemented. Their independence decision is `MANUAL_VERIFY`.

Message language:

- US: "미국 종목 감사인 자동 확인 미지원. EDGAR/10-K 등 원천 확인 필요."
- Japan: "일본 종목 감사인 자동 확인 미지원. EDINET/유가증권보고서 등 원천 확인 필요."

This avoids false comfort while still delivering the signal.

## Telegram Message Contract

Every alert starts with an explicit status line:

- `🚫 독립성 차단 — 매입 검토 금지`
- `🟡 독립성 확인 필요 — 원천 확인 전 매입 보류`
- `🟢 매수 시그널 — 독립성 차단 없음`

Message sections:

- status and reason
- symbol and market
- signal type, timeframe, price, stop, risk/reward
- conviction, score, status, daily trend
- heat warning from `atr_dot` and `sb_z_score`
- auditor section
- optional Korean enrichment section from 04 modules
- trace line with received time and source version

Blocked alerts are still sent, but the message must not include any "entry encouraged" phrasing.

## Heat And Quality Rules

MVP does not block solely because of heat. It flags risk:

- `atr_dot == true`: "ATR 과열봉"
- `sb_z_score > 2.5`: "시그마 과열"
- `conviction == "D"`: suppress primary buy alert and store as filtered signal.
- `ema_align == "역배열"`: suppress primary buy alert and store as filtered signal.

The `conviction == "D"` and reverse-alignment cases are not independence outcomes; they are signal-quality outcomes.

## Storage

Use SQLite with at least:

- raw payload JSON
- normalized ticker
- exchange
- market
- timeframe
- action
- base type
- independence status
- filter status
- received_at
- telegram_sent boolean

This supports a later `/feed` command and debugging TradingView alert delivery.

## TradingView CLI Watchlist Operations

The local TradingView CLI at `/Users/kjun/code/tradingview-mcp` can operate watchlists when TradingView Desktop is running with CDP enabled and the user is logged in.

Known useful commands:

```bash
cd /Users/kjun/code/tradingview-mcp
node src/cli/index.js watchlist get
node src/cli/index.js watchlist add NASDAQ:AAPL
node src/cli/index.js watchlist create "Intel Alert Candidates" --file /path/to/list.txt
```

`watchlist create` accepts symbols and `###Section` headings. This means the agent can help build or refresh watchlists from Market Insights candidates, but the user must have TradingView Desktop open in debug mode. This is an operating helper, not the alert source of truth. The source of truth for alert delivery is the TradingView alert configuration and the webhook payload.

## Error Handling

- Return 200 quickly after payload validation and process in the background.
- Invalid secret: 401.
- Invalid JSON or schema: 422 and no Telegram send.
- Telegram failure: log and mark `telegram_sent=false`.
- Enrichment failure: degrade the section and still send the independence alert.
- Auditor lookup failure: `MANUAL_VERIFY`, not `CLEAR`.

## Tests

Required deterministic tests:

- v6.2 payload parses, including `sb_z_score`.
- v6.1 fixture still parses with defaulted `sb_z_score`.
- BUY base type strips ` @SR↩`.
- SELL and CHECK do not create primary buy alerts.
- Korean blocked auditor returns `BLOCKED`.
- Korean clear auditor returns `CLEAR`.
- Korean missing auditor returns `MANUAL_VERIFY`.
- US and Japan return `MANUAL_VERIFY`.
- Telegram formatter status lines match the three decision classes.
- Dedup suppresses repeated same ticker/base type/timeframe within the configured window.
- Webhook endpoint stores and schedules processing after valid requests.

## Rollout

Phase 1 implements local webhook ingestion, decisions, formatting, storage, and tests.

Phase 2 wires the current 04 bot runtime and FastAPI alert server into one deployable process.

Phase 3 configures one real TradingView alert from the private indicator v6.2 JSON template and validates a live dry run.

Phase 4 optionally uses TradingView CLI to refresh watchlists from Market Insights candidates.

## Open Risks

- TradingView Desktop CLI operations can break after TradingView UI/internal updates.
- US/Japan auditor automation needs separate data-source design.
- The current 04 project has dirty local changes and limited tests; implementation must protect existing behavior.
- If the private indicator alert template is edited manually, malformed JSON or missing fields can break ingestion.
