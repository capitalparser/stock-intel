# Telegram Signal Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Telegram-first Lazy Alpha signal console that shows recent buy/sell/manual-review candidates and symbol-level signal details from the local signal ledger.

**Architecture:** Keep TradingView webhook ingestion as the source of truth for v1. Add query helpers on `SignalStore`, a small `signals.console` module for rolling-window filtering and Telegram text rendering, and Telegram command/callback handlers in `bot.py`. Inline keyboard buttons act like tabs by editing the same message with filter state encoded in callback data.

**Tech Stack:** Python 3.12, python-telegram-bot inline keyboards, SQLite, pytest/pytest-asyncio.

---

### Task 1: Signal Store Queries

**Files:**
- Modify: `signals/storage.py`
- Test: `tests/test_signal_console.py`

- [ ] **Step 1: Write failing tests for recent-window and ticker queries**

Create tests that insert fixture signal events, then assert recent-window filtering and ticker detail lookup.

- [ ] **Step 2: Run tests and confirm failure**

Run: `uv run pytest tests/test_signal_console.py -q`

Expected: tests fail because query helpers do not exist.

- [ ] **Step 3: Implement minimal store query methods**

Add `recent_since(since, limit=20)` and `latest_for_ticker(ticker)` to `SignalStore`.

- [ ] **Step 4: Run tests and confirm pass**

Run: `uv run pytest tests/test_signal_console.py -q`

Expected: tests pass.

### Task 2: Console State and Rendering

**Files:**
- Create: `signals/console.py`
- Test: `tests/test_signal_console.py`

- [ ] **Step 1: Write failing tests for default console rendering**

Assert `/signals` default is recent 8h, BUY tab, all markets, with rows grouped by latest events.

- [ ] **Step 2: Run tests and confirm failure**

Run: `uv run pytest tests/test_signal_console.py -q`

Expected: tests fail because `signals.console` does not exist.

- [ ] **Step 3: Implement console query and rendering**

Add `ConsoleState`, `parse_console_args`, `format_console`, `format_signal_detail`, and `build_console_keyboard`.

- [ ] **Step 4: Run tests and confirm pass**

Run: `uv run pytest tests/test_signal_console.py -q`

Expected: tests pass.

### Task 3: Telegram Commands and Buttons

**Files:**
- Modify: `bot.py`
- Test: `tests/test_bot_signal_console.py`

- [ ] **Step 1: Write failing handler tests**

Test `/signals`, `/buy`, `/sell`, and callback data `sig:tab=SELL|market=KR|hours=8` using a temporary `STATE_DB_PATH`.

- [ ] **Step 2: Run tests and confirm failure**

Run: `uv run pytest tests/test_bot_signal_console.py -q`

Expected: tests fail because handlers are not registered/exported.

- [ ] **Step 3: Implement Telegram handlers**

Add handlers for `/signals`, `/buy`, `/sell`, `/signal`, and callback pattern `^sig:`. Use message editing for callbacks and normal reply for commands.

- [ ] **Step 4: Run tests and confirm pass**

Run: `uv run pytest tests/test_bot_signal_console.py -q`

Expected: tests pass.

### Task 4: Docs and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document commands and defaults**

Document rolling window defaults, supported commands, and button tabs.

- [ ] **Step 2: Run full verification**

Run: `uv run pytest -q` and root `./Harness/verify.sh`.

- [ ] **Step 3: Commit**

Commit as `feat: add Telegram signal console`.

## Self-Review

- Spec coverage: covers rolling-window default, buy/sell/manual-review tabs, per-symbol detail, and Telegram button navigation.
- Placeholder scan: no TBD/TODO placeholders remain.
- Scope: v1 uses ledger-based current state only; live TradingView chart refresh remains a later v2.
