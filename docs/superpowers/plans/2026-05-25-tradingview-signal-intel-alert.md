# TradingView Signal Intel Alert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1 04_stock_intel alert pipeline: receive TradingView private-indicator v6.2 webhooks, run buy-signal and independence checks, store the event, and send a Telegram alert.

**Architecture:** Add a focused `signals/` package inside 04_stock_intel. Keep TradingView payload parsing, signal filtering, independence decisions, storage, formatting, and Telegram delivery in separate modules, then wire them into the existing FastAPI `alert_server.py`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, sqlite3, httpx, pytest, existing python-telegram-bot runtime.

---

## File Map

- Create `signals/__init__.py`: package marker.
- Create `signals/payload.py`: TradingView v6.2 Pydantic model and base-type helpers.
- Create `signals/market.py`: market classification for KR/US/JP/UNKNOWN.
- Create `signals/filtering.py`: buy-signal and quality filtering.
- Create `signals/independence.py`: blocked-auditor alias normalization and independence decision.
- Create `signals/storage.py`: SQLite event store for webhook payloads and decisions.
- Create `signals/formatting.py`: Telegram alert formatter.
- Create `signals/telegram.py`: Telegram Bot API sender with 4000-character chunking.
- Create `signals/pipeline.py`: orchestration for payload -> filter -> decision -> storage -> Telegram.
- Modify `alert_server.py`: add `POST /webhook/tradingview`, keep existing `POST /alert` compatibility route.
- Modify `pyproject.toml`: add pytest config and package build inclusion for `signals`.
- Create `tests/fixtures/tradingview_v6_2_buy_aapl.json`.
- Create `tests/fixtures/tradingview_v6_2_buy_samsung.json`.
- Create `tests/fixtures/tradingview_v6_2_sell_samsung.json`.
- Create `tests/test_signal_payload.py`.
- Create `tests/test_signal_filtering.py`.
- Create `tests/test_independence.py`.
- Create `tests/test_signal_formatting.py`.
- Create `tests/test_signal_storage.py`.
- Create `tests/test_signal_pipeline.py`.
- Create `tests/test_alert_server_tradingview.py`.

## Task 1: Test Tooling And Fixtures

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/fixtures/tradingview_v6_2_buy_aapl.json`
- Create: `tests/fixtures/tradingview_v6_2_buy_samsung.json`
- Create: `tests/fixtures/tradingview_v6_2_sell_samsung.json`

- [ ] **Step 1: Add pytest configuration and package inclusion**

Update `pyproject.toml` so the build includes `signals` and tests can run:

```toml
[tool.hatch.build.targets.wheel]
packages = ["data", "utils", "signals"]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "respx>=0.21.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "live: requires live external services. Deselected by default.",
]
addopts = "-m 'not live'"
```

- [ ] **Step 2: Add v6.2 BUY AAPL fixture**

Create `tests/fixtures/tradingview_v6_2_buy_aapl.json`:

```json
{
  "ticker": "AAPL",
  "name": "Apple Inc",
  "exchange": "NASDAQ",
  "timeframe": "240",
  "action": "BUY",
  "type": "💰 정석 진입 @SR↩",
  "price": 195.5,
  "sl": 188.2,
  "rr": 2.3,
  "desc": "눌림목/지지 진입",
  "market": "📈 강세 정렬",
  "ai_summary": "🎯 스나이퍼 타점 20 EMA 지지 반등",
  "score": 85,
  "status": "Green(GO)",
  "signal": "GP:수급 Sigma:PB ",
  "conviction": "S",
  "momentum": "",
  "momentum_sl": null,
  "momentum_tp": null,
  "momentum_bars": null,
  "energy": 2.85,
  "ema1_dist": 1.23,
  "candle_type": "양봉",
  "candle_strength": 82.5,
  "ema_touch": "ema1",
  "ema_align": "정배열",
  "daily_trend": "BULL",
  "daily_ema_aligned": true,
  "daily_rs": 78,
  "daily_above_200ma": true,
  "daily_setup_stage": "COMPLETE",
  "daily_volume_trend": "ACCUMULATION",
  "daily_dist_from_high": -3.2,
  "rsi2": 45.3,
  "upper_wick_pct": 8.2,
  "atr_multiple": 2.85,
  "atr_dot": false,
  "atr_dot_threshold": 7.0,
  "sb_z_score": 1.42
}
```

- [ ] **Step 3: Add v6.2 BUY Samsung fixture**

Create `tests/fixtures/tradingview_v6_2_buy_samsung.json` by copying the AAPL fixture and changing:

```json
{
  "ticker": "005930",
  "name": "삼성전자",
  "exchange": "KRX",
  "price": 71800,
  "sl": 70200,
  "rr": 2.1,
  "score": 75,
  "conviction": "A",
  "sb_z_score": 1.08
}
```

Keep all other required v6.2 fields present.

- [ ] **Step 4: Add SELL Samsung fixture**

Create `tests/fixtures/tradingview_v6_2_sell_samsung.json` by copying the Samsung fixture and changing:

```json
{
  "action": "SELL",
  "type": "💸 최종 청산 @SR↩",
  "desc": "추세 이탈/손절",
  "status": "Red(Wait)",
  "conviction": "D",
  "ema_align": "역배열",
  "sb_z_score": -2.15
}
```

- [ ] **Step 5: Run test discovery**

Run:

```bash
uv run pytest -q
```

Expected: pytest reports no tests or only existing import issues. If `pytest` is missing, run `uv sync --extra dev` first.

## Task 2: Payload And Market Domain

**Files:**
- Create: `signals/__init__.py`
- Create: `signals/payload.py`
- Create: `signals/market.py`
- Create: `tests/test_signal_payload.py`

- [ ] **Step 1: Write failing payload tests**

Create `tests/test_signal_payload.py`:

```python
import json
from pathlib import Path

from signals.market import classify_market
from signals.payload import TradingViewSignal


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_v6_2_payload_parses_sb_z_score():
    signal = TradingViewSignal.model_validate(load_fixture("tradingview_v6_2_buy_aapl.json"))
    assert signal.schema_version == "v6.2"
    assert signal.sb_z_score == 1.42
    assert signal.base_type() == "💰 정석 진입"
    assert signal.has_sr_flip() is True


def test_market_classification():
    assert classify_market("005930", "KRX").code == "KR"
    assert classify_market("AAPL", "NASDAQ").code == "US"
    assert classify_market("7203", "TSE").code == "JP"
    assert classify_market("ABC", "").code == "UNKNOWN"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/test_signal_payload.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'signals'`.

- [ ] **Step 3: Implement `signals/payload.py` and `signals/market.py`**

Create the package marker:

```python
# signals/__init__.py
```

Create `signals/payload.py` with the v6.2 Pydantic model. Reuse the field names from the fixture and add:

```python
schema_version: str = "v6.2"
sb_z_score: float = 0.0

def base_type(self) -> str:
    return self.type.removesuffix(" @SR↩").strip()

def has_sr_flip(self) -> bool:
    return self.type.endswith(" @SR↩")
```

Create `signals/market.py` with:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    code: str
    label: str


def classify_market(ticker: str, exchange: str) -> Market:
    ex = (exchange or "").upper()
    if ex in {"KRX", "KOSPI", "KOSDAQ", "KONEX"} or ticker.isdigit() and len(ticker) == 6:
        return Market("KR", "한국")
    if ex in {"NASDAQ", "NYSE", "AMEX", "ARCA", "BATS", "OTC"}:
        return Market("US", "미국")
    if ex in {"TSE", "TYO", "JPX"}:
        return Market("JP", "일본")
    return Market("UNKNOWN", "미분류")
```

- [ ] **Step 4: Run payload tests**

Run:

```bash
uv run pytest tests/test_signal_payload.py -q
```

Expected: PASS.

## Task 3: Filtering

**Files:**
- Create: `signals/filtering.py`
- Create: `tests/test_signal_filtering.py`

- [ ] **Step 1: Write filtering tests**

Create tests for:

```python
def test_buy_signal_allowed_for_base_type_with_sr_suffix()
def test_sell_signal_filtered()
def test_conviction_d_filtered()
def test_reverse_ema_alignment_filtered()
```

Expected behavior:

- AAPL BUY fixture passes.
- Samsung SELL fixture returns filtered with reason containing `action=SELL`.
- BUY with `conviction="D"` returns filtered with reason containing `conviction`.
- BUY with `ema_align="역배열"` returns filtered with reason containing `ema_align`.

- [ ] **Step 2: Implement filtering**

Create:

```python
BUY_BASE_TYPES = {
    "💰 정석 진입",
    "🚀 돌파 진입",
    "⚡ 공격 진입",
    "🔼 피라미딩 추매",
    "📈 모멘텀 BUY",
    "PEG Pullback",
    "PEG Rebreak",
}
```

Return a dataclass:

```python
@dataclass(frozen=True)
class FilterDecision:
    allowed: bool
    status: str
    reason: str
```

Implement `decide_signal_filter(signal)`.

- [ ] **Step 3: Run filtering tests**

Run:

```bash
uv run pytest tests/test_signal_filtering.py -q
```

Expected: PASS.

## Task 4: Independence Decision

**Files:**
- Create: `signals/independence.py`
- Create: `tests/test_independence.py`

- [ ] **Step 1: Write independence tests**

Cover:

- Korean audit dict with current firm `삼정회계법인` returns `BLOCKED`.
- Korean audit dict with current firm `한영회계법인` returns `CLEAR`.
- Korean audit dict with `{"error": "..."}` returns `MANUAL_VERIFY`.
- US market returns `MANUAL_VERIFY` with EDGAR wording.
- Japan market returns `MANUAL_VERIFY` with EDINET wording.

- [ ] **Step 2: Implement independence**

Create:

```python
BLOCKED_ALIASES = {
    "삼정회계법인": "삼정회계법인",
    "삼정KPMG": "삼정회계법인",
    "삼정 KPMG": "삼정회계법인",
    "KPMG삼정": "삼정회계법인",
}
```

Create:

```python
@dataclass(frozen=True)
class IndependenceDecision:
    status: str
    reason: str
    auditor: str | None = None
```

Implement `decide_independence(market, audit_firm)`.

- [ ] **Step 3: Run tests**

Run:

```bash
uv run pytest tests/test_independence.py -q
```

Expected: PASS.

## Task 5: Storage

**Files:**
- Create: `signals/storage.py`
- Create: `tests/test_signal_storage.py`

- [ ] **Step 1: Write storage tests**

Test `SignalStore.put_event()` and `SignalStore.recent(limit=10)` store:

- ticker
- exchange
- market
- timeframe
- action
- base_type
- independence_status
- filter_status
- payload_json
- telegram_sent

- [ ] **Step 2: Implement SQLite store**

Create schema:

```sql
CREATE TABLE IF NOT EXISTS signal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    exchange TEXT NOT NULL,
    market TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    action TEXT NOT NULL,
    base_type TEXT NOT NULL,
    independence_status TEXT NOT NULL,
    filter_status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    telegram_sent INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_signal_events_received
    ON signal_events(received_at DESC);
```

- [ ] **Step 3: Run storage tests**

Run:

```bash
uv run pytest tests/test_signal_storage.py -q
```

Expected: PASS.

## Task 6: Telegram Formatting And Sender

**Files:**
- Create: `signals/formatting.py`
- Create: `signals/telegram.py`
- Create: `tests/test_signal_formatting.py`

- [ ] **Step 1: Write formatter tests**

Assert first lines:

- `🚫 독립성 차단 — 매입 검토 금지`
- `🟡 독립성 확인 필요 — 원천 확인 전 매입 보류`
- `🟢 매수 시그널 — 독립성 차단 없음`

Assert heat warning includes `시그마 과열` when `sb_z_score > 2.5`.

- [ ] **Step 2: Implement formatter**

Create `format_signal_alert(signal, market, filter_decision, independence_decision, audit_firm=None) -> str`.

Include:

- symbol line
- signal line
- price/risk line
- quality line
- heat line
- independence/auditor line
- trace line

- [ ] **Step 3: Implement Telegram sender**

Create `send_telegram_message(bot_token, chat_ids, text)` using `httpx.AsyncClient` and chunks of 4000 characters. If token or chat IDs are empty, log and return `False`.

- [ ] **Step 4: Run formatter tests**

Run:

```bash
uv run pytest tests/test_signal_formatting.py -q
```

Expected: PASS.

## Task 7: Pipeline

**Files:**
- Create: `signals/pipeline.py`
- Create: `tests/test_signal_pipeline.py`

- [ ] **Step 1: Write fake-backed pipeline tests**

Use fake functions:

- `fetch_audit_firm=lambda ticker: {"recent": [{"year": 2025, "firm": "삼정회계법인"}], "current_firm": "삼정회계법인"}`
- `send_message=lambda text: sent.append(text) or True`

Assert:

- blocked Korean BUY stores event and sends blocked Telegram text.
- US BUY sends manual verify text.
- SELL stores filtered event and does not send primary Telegram alert.

- [ ] **Step 2: Implement pipeline**

Create `SignalPipeline` with dependencies:

- store
- audit lookup function
- async sender function

Implement `handle_payload(payload: dict) -> PipelineResult`.

- [ ] **Step 3: Run pipeline tests**

Run:

```bash
uv run pytest tests/test_signal_pipeline.py -q
```

Expected: PASS.

## Task 8: FastAPI Route Wiring

**Files:**
- Modify: `alert_server.py`
- Create: `tests/test_alert_server_tradingview.py`

- [ ] **Step 1: Write endpoint tests**

Use `TestClient` and monkeypatch the app state pipeline.

Tests:

- invalid secret returns 401.
- invalid payload returns 422.
- valid v6.2 payload returns `{"received": true, "ticker": "AAPL"}`.

- [ ] **Step 2: Add settings and route**

In `alert_server.py`, add:

- `WEBHOOK_SECRET`
- `STATE_DB_PATH`
- `SIGNAL_CHAT_IDS`, falling back to `ALLOWED_CHAT_IDS`
- `POST /webhook/tradingview`

The route should validate the secret and schedule processing with `BackgroundTasks`.

- [ ] **Step 3: Preserve old `/alert`**

Do not delete existing `/alert`. Keep it for compatibility while the new route becomes canonical.

- [ ] **Step 4: Run endpoint tests**

Run:

```bash
uv run pytest tests/test_alert_server_tradingview.py -q
```

Expected: PASS.

## Task 9: Full Verification And Docs

**Files:**
- Modify: `README.md`
- Modify: `CONTEXT.md`

- [ ] **Step 1: Update README**

Add:

```text
TradingView webhook URL:
https://<host>/webhook/tradingview?secret=<WEBHOOK_SECRET>
```

Add the v6.2 payload reference and explain KR/US/JP independence behavior.

- [ ] **Step 2: Update CONTEXT**

Define:

- signal alert
- independence decision
- blocked auditor
- manual verify
- market support state
- TradingView CLI watchlist helper

- [ ] **Step 3: Run all deterministic tests**

Run:

```bash
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Run Harness verification**

Run from vault root:

```bash
cd /Users/kjun/vault
./Harness/verify.sh
```

Expected: `harness verify ok` and related checks pass.

## Execution Notes

The repository has existing local changes and untracked files. Do not revert them. Stage only files touched for this feature.

TradingView CLI watchlist work is operational follow-up after the webhook pipeline exists. It requires TradingView Desktop running with `--remote-debugging-port=9222`.
