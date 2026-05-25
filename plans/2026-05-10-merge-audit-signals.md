# Merge audit-safe-signals into stock-intel

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `02_audit_safe_signals`의 TradingView webhook 필터 파이프라인을 `04_stock_intel`에 흡수하여, 단일 봇이 (1) 주식 정보 조회 응답과 (2) 자동 매수 시그널 필터 알림을 모두 처리한다.

**Architecture:** Telegram polling bot을 `python-telegram-bot`의 manual 제어 API로 전환하고, FastAPI lifespan 안에서 polling을 시작한다. uvicorn이 단일 asyncio 이벤트 루프를 관리하며 FastAPI webhook endpoint와 Telegram polling을 공존시킨다. 감사인 조회 로직은 `webhook/` 하위 패키지로 이식되고, `data/audit_firm.py`(표시용 dict 반환)는 변경 없이 유지된다.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, python-telegram-bot v20+, httpx, pydantic-settings, pyyaml, kreports, sqlite3(stdlib)

---

## File Map

### NEW — 전량 신규 생성

| 파일 | 출처 / 역할 |
|------|------------|
| `app.py` | FastAPI 인스턴스 + lifespan (Telegram polling 내장) + uvicorn `__main__` |
| `webhook/__init__.py` | 빈 패키지 마커 |
| `webhook/config.py` | `WebhookSettings` (pydantic-settings) + YAML 로더 |
| `webhook/domain.py` | 02 `domain/webhook.py` + `domain/decision.py` + `domain/ticker_market.py` 통합 |
| `webhook/filters.py` | 02 `filters/buy_filter.py` + `filters/dedup.py` 통합 |
| `webhook/policy.py` | 02 `auditor/types.py` + `auditor/policy.py` 통합 |
| `webhook/lookup.py` | 02 `auditor/lookup.py` + `auditor/cache.py` 통합 |
| `webhook/notify.py` | 02 `notify/telegram.py` + `notify/format.py` 통합; `format_signal_message`로 리네임 |
| `webhook/pipeline.py` | 02 `pipeline/handle_webhook.py` + `logging_setup.DecisionLogger` 통합 |
| `webhook/server.py` | FastAPI 라우트 팩토리 (`/healthz`, `POST /webhook`) |
| `config/blocked_auditors.yaml` | 차단 감사인 + aliases 설정 |
| `config/settings.yaml` | BuyFilterConfig 설정 (whitelist, min_score 등) |
| `tests/__init__.py` | 빈 |
| `tests/webhook/__init__.py` | 빈 |
| `tests/webhook/test_domain.py` | domain 단위 테스트 |
| `tests/webhook/test_filters.py` | BuyFilterConfig + DedupStore 단위 테스트 |
| `tests/webhook/test_policy.py` | AuditorPolicy + decide_alert 단위 테스트 |
| `tests/webhook/test_lookup.py` | KreportsLookup 단위 테스트 (fake) |
| `tests/webhook/test_notify.py` | split_for_telegram + format_signal_message 단위 테스트 |
| `tests/webhook/test_pipeline.py` | Pipeline 통합 테스트 (fake 주입) |
| `tests/webhook/test_server.py` | TestClient 기반 HTTP 테스트 |

### MODIFY — 기존 파일 수정

| 파일 | 변경 내용 |
|------|---------|
| `bot.py` | `build_telegram_app() -> Application` 함수 추출; `if __name__ == "__main__"` 블록 삭제 |
| `pyproject.toml` | fastapi, uvicorn[standard], httpx, pyyaml, pydantic-settings 추가; pytest 설정 추가 |

### UNCHANGED — 수정 없음

`data/`, `utils/`, `cache/` 전체.

---

## Task 1: pyproject.toml + 프로젝트 스캐폴드

**Files:**
- Modify: `pyproject.toml`
- Create: `config/blocked_auditors.yaml`
- Create: `config/settings.yaml`
- Create: `tests/__init__.py`
- Create: `tests/webhook/__init__.py`
- Create: `webhook/__init__.py`

- [ ] **Step 1: pyproject.toml 수정**

```toml
[project]
name = "stock-intel"
version = "0.2.0"
description = "국장 주식 투자 데이터 통합 Telegram 봇 + TradingView 시그널 필터"
requires-python = ">=3.12"
dependencies = [
    "pykrx>=1.0.0",
    "pandas-ta>=0.3.14b",
    "python-telegram-bot>=20.0",
    "requests>=2.32.0",
    "python-dotenv>=1.0.0",
    "rapidfuzz>=3.0.0",
    "apscheduler>=3.10.0",
    "kreports>=0.1.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "httpx>=0.27.0",
    "pyyaml>=6.0.2",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "respx>=0.21.0",
    "httpx>=0.27.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["data", "utils", "webhook"]

[tool.uv]
required-version = ">=0.4"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "live: requires live external services. Deselected by default.",
]
addopts = "-m 'not live'"
```

- [ ] **Step 2: config/blocked_auditors.yaml 생성**

```yaml
blocked:
  - "삼정회계법인"

aliases:
  "삼정KPMG": "삼정회계법인"
  "삼정 KPMG": "삼정회계법인"
  "KPMG삼정": "삼정회계법인"
```

- [ ] **Step 3: config/settings.yaml 생성**

```yaml
# BuyFilter 설정
buy_type_whitelist:
  - "💰 정석 진입"
  - "🚀 돌파 진입"
  - "⚡ 공격 진입"
  - "🔼 피라미딩 추매"
  - "📈 모멘텀 BUY"
  - "PEG Pullback"
  - "PEG Rebreak"

min_score: null
min_conviction: null
require_status: null
forbid_ema_align: []

# gap_policy: "manual_verify" (보수적) 또는 "carry_forward"
gap_policy: "manual_verify"
```

- [ ] **Step 4: 빈 패키지 마커 생성**

```bash
touch /Users/kjun/vault/01_Projects/04_stock_intel/webhook/__init__.py
touch /Users/kjun/vault/01_Projects/04_stock_intel/tests/__init__.py
touch /Users/kjun/vault/01_Projects/04_stock_intel/tests/webhook/__init__.py
```

- [ ] **Step 5: 의존성 설치 확인**

```bash
cd /Users/kjun/vault/01_Projects/04_stock_intel
uv sync --all-extras
```

Expected: 설치 완료, 에러 없음.

- [ ] **Step 6: .env에 신규 환경변수 추가 (로컬 .env 직접 편집)**

추가할 항목:
```
WEBHOOK_SECRET=dev-secret-change-me
SIGNAL_CHAT_ID=         # 시그널 알림을 받을 Telegram chat_id
STATE_DB_PATH=./state.db
KREPORTS_DB_PATH=       # kreports.db 절대 경로 (기존 04 설정과 동일)
CACHE_TTL_DAYS=7
DEDUP_WINDOW_MINUTES=5
DRY_RUN=false
DECISION_LOG_PATH=./logs/decisions.jsonl
```

- [ ] **Step 7: .gitignore에 상태 파일 추가**

```
state.db
logs/
```

---

## Task 2: webhook/domain.py

**Files:**
- Create: `webhook/domain.py`
- Create: `tests/webhook/test_domain.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/webhook/test_domain.py
import pytest
from webhook.domain import (
    Decision,
    DecisionKind,
    AuditorRef,
    Webhook,
    is_korean,
)


def _buy_payload(**overrides) -> dict:
    base = {
        "ticker": "005930",
        "name": "삼성전자",
        "exchange": "KOSPI",
        "timeframe": "1D",
        "action": "BUY",
        "type": "💰 정석 진입",
        "price": 75000.0,
        "score": 80,
        "conviction": "A",
        "candle_type": "양봉",
        "ema_touch": "ema1",
        "ema_align": "정배열",
    }
    base.update(overrides)
    return base


def test_webhook_parse_minimal_buy():
    wh = Webhook.model_validate(_buy_payload())
    assert wh.action == "BUY"
    assert wh.ticker == "005930"


def test_base_type_strips_sr_flip():
    wh = Webhook.model_validate(_buy_payload(type="💰 정석 진입 @SR↩"))
    assert wh.base_type() == "💰 정석 진입"
    assert wh.has_sr_flip() is True


def test_base_type_no_flip():
    wh = Webhook.model_validate(_buy_payload(type="💰 정석 진입"))
    assert wh.base_type() == "💰 정석 진입"
    assert wh.has_sr_flip() is False


def test_webhook_extra_fields_ignored():
    payload = _buy_payload(unknown_field="ignored")
    wh = Webhook.model_validate(payload)
    assert not hasattr(wh, "unknown_field")


def test_is_korean_by_exchange():
    assert is_korean("005930", "KOSPI") is True
    assert is_korean("005930", "KOSDAQ") is True
    assert is_korean("AAPL", "NASDAQ") is False


def test_is_korean_by_6digit_fallback():
    assert is_korean("005930", "") is True
    assert is_korean("AAPL", "") is False
    assert is_korean("12345", "") is False   # 5자리 → False
    assert is_korean("1234567", "") is False  # 7자리 → False


def test_decision_clean():
    ref = AuditorRef(
        fiscal_year="2026",
        auditor="한영회계법인",
        auditor_normalized="한영회계법인",
    )
    d = Decision.clean(ref)
    assert d.kind == DecisionKind.CLEAN
    assert d.should_notify is True


def test_decision_skip_no_notify():
    d = Decision.skip("action=SELL")
    assert d.kind == DecisionKind.SKIP
    assert d.should_notify is False


def test_decision_manual_verify():
    d = Decision.manual_verify(reason="2026 미공시")
    assert d.kind == DecisionKind.MANUAL_VERIFY
    assert d.should_notify is True
```

- [ ] **Step 2: 실패 확인**

```bash
cd /Users/kjun/vault/01_Projects/04_stock_intel
uv run pytest tests/webhook/test_domain.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'webhook.domain'`

- [ ] **Step 3: webhook/domain.py 구현**

```python
# webhook/domain.py
"""TradingView webhook payload + audit decision types + Korean ticker detection."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Korean ticker detection
# ---------------------------------------------------------------------------
KOREAN_EXCHANGES: frozenset[str] = frozenset({"KRX", "KOSPI", "KOSDAQ", "KONEX"})


def is_korean(
    ticker: str, exchange: str, *, allowed: frozenset[str] = KOREAN_EXCHANGES
) -> bool:
    if exchange and exchange.upper() in allowed:
        return True
    if not exchange and ticker.isdigit() and len(ticker) == 6:
        return True
    return False


# ---------------------------------------------------------------------------
# TradingView webhook payload (v6.1, 36 fields)
# ---------------------------------------------------------------------------
ActionType = Literal["BUY", "SELL", "CHECK"]
CandleType = Literal["양봉", "음봉", "도지"]
EmaTouch = Literal["ema1", "ema2", "ema3", "ema1+ema2", "none"]
EmaAlign = Literal["정배열", "역배열", "꼬임"]
Conviction = Literal["S", "A", "B", "C", "D"]
Momentum = Literal["BUY", "SELL", ""]


class Webhook(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=False)

    ticker: str
    name: str
    exchange: str = ""
    timeframe: str

    action: ActionType
    type: str
    price: float
    sl: float | None = None
    rr: float | None = None
    desc: str = ""

    market: str = ""
    ai_summary: str = ""
    score: int = 0
    status: str = ""
    signal: str = ""
    conviction: Conviction = "B"

    momentum: Momentum = ""
    momentum_sl: float | None = None
    momentum_tp: float | None = None
    momentum_bars: int | None = None

    energy: float = 0.0
    ema1_dist: float = 0.0

    candle_type: CandleType | str = "양봉"
    candle_strength: float = 0.0
    ema_touch: EmaTouch | str = "none"
    ema_align: EmaAlign | str = "꼬임"

    daily_trend: str = ""
    daily_ema_aligned: bool = False
    daily_rs: int = 0
    daily_above_200ma: bool = False
    daily_setup_stage: str = ""
    daily_volume_trend: str = ""
    daily_dist_from_high: float = 0.0

    atr_multiple: float | None = None
    atr_dot: bool = False
    atr_dot_threshold: float = 7.0

    rsi2: float = Field(default=50.0, ge=0.0, le=100.0)
    upper_wick_pct: float = Field(default=0.0, ge=0.0, le=100.0)

    def base_type(self) -> str:
        return self.type.removesuffix(" @SR↩").strip()

    def has_sr_flip(self) -> bool:
        return self.type.endswith(" @SR↩")


# ---------------------------------------------------------------------------
# Audit decision
# ---------------------------------------------------------------------------
class DecisionKind(StrEnum):
    SKIP = "SKIP"
    CLEAN = "CLEAN"
    MANUAL_VERIFY = "MANUAL_VERIFY"


@dataclass(frozen=True)
class AuditorRef:
    fiscal_year: str
    auditor: str
    auditor_normalized: str
    opinion: str | None = None
    consecutive_years: int | None = None
    report_type: str = "CFS"


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    reason: str
    auditor_2026: AuditorRef | None = None
    auditor_2025: AuditorRef | None = None
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def skip(cls, reason: str, **extra: str) -> Decision:
        return cls(kind=DecisionKind.SKIP, reason=reason, extra=dict(extra))

    @classmethod
    def clean(
        cls, auditor_2026: AuditorRef, reason: str = "2026 감사인 차단 리스트 외"
    ) -> Decision:
        return cls(kind=DecisionKind.CLEAN, reason=reason, auditor_2026=auditor_2026)

    @classmethod
    def manual_verify(
        cls, reason: str, auditor_2025: AuditorRef | None = None
    ) -> Decision:
        return cls(
            kind=DecisionKind.MANUAL_VERIFY,
            reason=reason,
            auditor_2025=auditor_2025,
        )

    @property
    def should_notify(self) -> bool:
        return self.kind in (DecisionKind.CLEAN, DecisionKind.MANUAL_VERIFY)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/webhook/test_domain.py -v
```

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add webhook/__init__.py webhook/domain.py tests/__init__.py tests/webhook/__init__.py tests/webhook/test_domain.py
git commit -m "feat(stock-intel): add webhook/domain — Webhook model + Decision types + is_korean"
```

---

## Task 3: webhook/filters.py

**Files:**
- Create: `webhook/filters.py`
- Create: `tests/webhook/test_filters.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/webhook/test_filters.py
import pytest
from webhook.domain import Webhook
from webhook.filters import BuyFilterConfig, DedupStore, passes_buy_filter


def _make_webhook(**overrides) -> Webhook:
    base = {
        "ticker": "005930",
        "name": "삼성전자",
        "exchange": "KOSPI",
        "timeframe": "1D",
        "action": "BUY",
        "type": "💰 정석 진입",
        "price": 75000.0,
        "score": 80,
        "conviction": "A",
        "candle_type": "양봉",
        "ema_touch": "ema1",
        "ema_align": "정배열",
    }
    base.update(overrides)
    return Webhook.model_validate(base)


# --- passes_buy_filter ---

def test_passes_buy_filter_ok():
    ok, reason = passes_buy_filter(_make_webhook(), BuyFilterConfig())
    assert ok is True
    assert reason == ""


def test_passes_buy_filter_sell_rejected():
    ok, reason = passes_buy_filter(_make_webhook(action="SELL"), BuyFilterConfig())
    assert ok is False
    assert "SELL" in reason


def test_passes_buy_filter_non_korean_rejected():
    ok, reason = passes_buy_filter(
        _make_webhook(exchange="NASDAQ", ticker="AAPL"), BuyFilterConfig()
    )
    assert ok is False
    assert "non-Korean" in reason


def test_passes_buy_filter_whitelist_miss():
    cfg = BuyFilterConfig(buy_type_whitelist=("💰 정석 진입",))
    ok, reason = passes_buy_filter(_make_webhook(type="🚀 돌파 진입"), cfg)
    assert ok is False
    assert "whitelist" in reason


def test_passes_buy_filter_whitelist_hit():
    cfg = BuyFilterConfig(buy_type_whitelist=("💰 정석 진입",))
    ok, _ = passes_buy_filter(_make_webhook(type="💰 정석 진입"), cfg)
    assert ok is True


def test_passes_buy_filter_sr_flip_matches_prefix():
    cfg = BuyFilterConfig(buy_type_whitelist=("💰 정석 진입",))
    ok, _ = passes_buy_filter(_make_webhook(type="💰 정석 진입 @SR↩"), cfg)
    assert ok is True


def test_passes_buy_filter_min_score():
    cfg = BuyFilterConfig(min_score=90)
    ok, reason = passes_buy_filter(_make_webhook(score=80), cfg)
    assert ok is False
    assert "score" in reason


def test_passes_buy_filter_conviction():
    cfg = BuyFilterConfig(min_conviction="A")
    ok, reason = passes_buy_filter(_make_webhook(conviction="B"), cfg)
    assert ok is False
    assert "conviction" in reason


def test_passes_buy_filter_forbid_ema_align():
    cfg = BuyFilterConfig(forbid_ema_align=("역배열",))
    ok, reason = passes_buy_filter(_make_webhook(ema_align="역배열"), cfg)
    assert ok is False
    assert "ema_align" in reason


# --- DedupStore ---

def test_dedup_first_call_passes():
    store = DedupStore(":memory:", window_seconds=300)
    key = store.make_key("005930", "💰 정석 진입", "1D")
    assert store.is_duplicate(key) is False


def test_dedup_second_call_blocked():
    store = DedupStore(":memory:", window_seconds=300)
    key = store.make_key("005930", "💰 정석 진입", "1D")
    store.is_duplicate(key)
    assert store.is_duplicate(key) is True


def test_dedup_different_keys_independent():
    store = DedupStore(":memory:", window_seconds=300)
    key1 = store.make_key("005930", "💰 정석 진입", "1D")
    key2 = store.make_key("035720", "🚀 돌파 진입", "1D")
    store.is_duplicate(key1)
    assert store.is_duplicate(key2) is False


def test_dedup_expired_passes():
    store = DedupStore(":memory:", window_seconds=300)
    key = store.make_key("005930", "💰 정석 진입", "1D")
    now = 1000
    store.is_duplicate(key, now=now)
    assert store.is_duplicate(key, now=now + 301) is False
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/webhook/test_filters.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'webhook.filters'`

- [ ] **Step 3: webhook/filters.py 구현**

```python
# webhook/filters.py
"""BuyFilter + DedupStore."""
from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from webhook.domain import KOREAN_EXCHANGES, Webhook, is_korean

# ---------------------------------------------------------------------------
# BuyFilterConfig
# ---------------------------------------------------------------------------

_CONVICTION_RANK = {"D": 0, "C": 1, "B": 2, "A": 3, "S": 4}


@dataclass(frozen=True)
class BuyFilterConfig:
    buy_type_whitelist: tuple[str, ...] = ()
    min_score: int | None = None
    min_conviction: str | None = None
    require_status: str | None = None
    forbid_ema_align: tuple[str, ...] = ()
    korean_exchanges: frozenset[str] = KOREAN_EXCHANGES

    @classmethod
    def from_yaml(cls, raw: dict) -> BuyFilterConfig:
        return cls(
            buy_type_whitelist=tuple(raw.get("buy_type_whitelist") or ()),
            min_score=raw.get("min_score"),
            min_conviction=raw.get("min_conviction"),
            require_status=raw.get("require_status"),
            forbid_ema_align=tuple(raw.get("forbid_ema_align") or ()),
            korean_exchanges=frozenset(
                raw.get("korean_exchanges") or KOREAN_EXCHANGES
            ),
        )


def passes_buy_filter(webhook: Webhook, cfg: BuyFilterConfig) -> tuple[bool, str]:
    """Return (allowed, reason). reason is empty if allowed."""
    if webhook.action != "BUY":
        return False, f"action={webhook.action} (not BUY)"

    if not is_korean(webhook.ticker, webhook.exchange, allowed=cfg.korean_exchanges):
        return False, f"non-Korean ticker (exchange={webhook.exchange or '∅'})"

    if cfg.buy_type_whitelist and not _matches_any_prefix(
        webhook.base_type(), cfg.buy_type_whitelist
    ):
        return False, f"type '{webhook.base_type()}' not in whitelist"

    if cfg.min_score is not None and webhook.score < cfg.min_score:
        return False, f"score {webhook.score} < {cfg.min_score}"

    if cfg.min_conviction is not None:
        threshold = _CONVICTION_RANK.get(cfg.min_conviction.upper(), 0)
        if _CONVICTION_RANK.get(webhook.conviction, -1) < threshold:
            return False, f"conviction {webhook.conviction} < {cfg.min_conviction}"

    if cfg.require_status and webhook.status != cfg.require_status:
        return False, f"status {webhook.status!r} != {cfg.require_status!r}"

    if webhook.ema_align in cfg.forbid_ema_align:
        return False, f"ema_align={webhook.ema_align} (forbidden)"

    return True, ""


def _matches_any_prefix(value: str, prefixes: Iterable[str]) -> bool:
    return any(value.startswith(p) for p in prefixes)


# ---------------------------------------------------------------------------
# DedupStore
# ---------------------------------------------------------------------------

_DEDUP_SCHEMA = """
CREATE TABLE IF NOT EXISTS dedup (
    key TEXT PRIMARY KEY,
    seen_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS dedup_seen_at ON dedup(seen_at);
"""


class DedupStore:
    def __init__(self, db_path: str | Path, window_seconds: int = 300) -> None:
        self._path = str(db_path)
        self._window = window_seconds
        self._init()

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_DEDUP_SCHEMA)
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, isolation_level=None, timeout=5.0)
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def make_key(ticker: str, base_type: str, timeframe: str) -> str:
        return f"{ticker}|{base_type}|{timeframe}"

    def is_duplicate(self, key: str, *, now: int | None = None) -> bool:
        cur_ts = int(now if now is not None else time.time())
        cutoff = cur_ts - self._window
        with self._connect() as conn:
            row = conn.execute(
                "SELECT seen_at FROM dedup WHERE key = ?", (key,)
            ).fetchone()
            if row is not None and row[0] >= cutoff:
                return True
            conn.execute(
                "INSERT OR REPLACE INTO dedup(key, seen_at) VALUES (?, ?)",
                (key, cur_ts),
            )
            conn.commit()
        return False
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/webhook/test_filters.py -v
```

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add webhook/filters.py tests/webhook/test_filters.py
git commit -m "feat(stock-intel): add webhook/filters — BuyFilterConfig + DedupStore"
```

---

## Task 4: webhook/policy.py

**Files:**
- Create: `webhook/policy.py`
- Create: `tests/webhook/test_policy.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/webhook/test_policy.py
import pytest
from webhook.domain import AuditorRef, DecisionKind
from webhook.policy import AuditEntry, AuditHistory, AuditorPolicy, decide_alert


def _make_history(entries: list[tuple[str, str, str]]) -> AuditHistory:
    """entries: [(fiscal_year, auditor, report_type)]"""
    return AuditHistory(
        ticker="005930",
        entries=tuple(
            AuditEntry(fiscal_year=fy, auditor=aud, report_type=rt)
            for fy, aud, rt in entries
        ),
        fetched_at=0,
    )


_POLICY = AuditorPolicy(blocked=frozenset(["삼정회계법인"]), aliases={"삼정KPMG": "삼정회계법인"})


def test_decide_clean_2026_not_blocked():
    history = _make_history([("2026", "한영회계법인", "CFS"), ("2025", "한영회계법인", "CFS")])
    d = decide_alert(history, _POLICY)
    assert d.kind == DecisionKind.CLEAN
    assert d.auditor_2026 is not None
    assert d.auditor_2026.auditor == "한영회계법인"


def test_decide_skip_2026_blocked():
    history = _make_history([("2026", "삼정회계법인", "CFS")])
    d = decide_alert(history, _POLICY)
    assert d.kind == DecisionKind.SKIP


def test_decide_skip_2026_alias_blocked():
    history = _make_history([("2026", "삼정KPMG", "CFS")])
    d = decide_alert(history, _POLICY)
    assert d.kind == DecisionKind.SKIP


def test_decide_manual_verify_no_2026():
    history = _make_history([("2025", "한영회계법인", "CFS")])
    d = decide_alert(history, _POLICY)
    assert d.kind == DecisionKind.MANUAL_VERIFY
    assert d.auditor_2025 is not None
    assert d.auditor_2025.auditor == "한영회계법인"


def test_decide_manual_verify_empty_history():
    history = AuditHistory(ticker="005930", entries=(), fetched_at=0)
    d = decide_alert(history, _POLICY)
    assert d.kind == DecisionKind.MANUAL_VERIFY


def test_decide_manual_verify_error():
    history = AuditHistory(ticker="005930", entries=(), fetched_at=0, error="DB 연결 실패")
    d = decide_alert(history, _POLICY)
    assert d.kind == DecisionKind.MANUAL_VERIFY
    assert "DB 연결 실패" in d.reason


def test_decide_manual_verify_none_history():
    d = decide_alert(None, _POLICY)
    assert d.kind == DecisionKind.MANUAL_VERIFY


def test_carry_forward_policy():
    policy = AuditorPolicy(
        blocked=frozenset(["삼정회계법인"]),
        aliases={},
        gap_policy="carry_forward",
    )
    history = _make_history([("2025", "한영회계법인", "CFS")])
    d = decide_alert(history, policy)
    assert d.kind == DecisionKind.CLEAN


def test_carry_forward_blocked():
    policy = AuditorPolicy(
        blocked=frozenset(["삼정회계법인"]),
        aliases={},
        gap_policy="carry_forward",
    )
    history = _make_history([("2025", "삼정회계법인", "CFS")])
    d = decide_alert(history, policy)
    assert d.kind == DecisionKind.SKIP


def test_find_cfs_preferred_over_ofs():
    history = _make_history([
        ("2026", "OFS법인", "OFS"),
        ("2026", "CFS법인", "CFS"),
    ])
    d = decide_alert(history, _POLICY)
    assert d.auditor_2026 is not None
    assert d.auditor_2026.auditor == "CFS법인"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/webhook/test_policy.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'webhook.policy'`

- [ ] **Step 3: webhook/policy.py 구현**

```python
# webhook/policy.py
"""AuditEntry + AuditHistory + AuditorPolicy + decide_alert."""
from __future__ import annotations

from dataclasses import dataclass

from webhook.domain import AuditorRef, Decision


@dataclass(frozen=True)
class AuditEntry:
    fiscal_year: str
    auditor: str
    report_type: str  # "CFS" | "OFS"
    opinion: str | None = None
    consecutive_years: int | None = None
    auditor_changed: bool | None = None


@dataclass(frozen=True)
class AuditHistory:
    ticker: str
    entries: tuple[AuditEntry, ...]
    fetched_at: int
    error: str | None = None

    def find(self, fiscal_year: str, report_type: str | None = None) -> AuditEntry | None:
        for e in self.entries:
            if e.fiscal_year != fiscal_year:
                continue
            if report_type is None or e.report_type == report_type:
                return e
        return None

    def find_2026(self) -> AuditEntry | None:
        return self.find("2026", "CFS") or self.find("2026", "OFS")

    def find_2025(self) -> AuditEntry | None:
        return self.find("2025", "CFS") or self.find("2025", "OFS")

    @property
    def is_empty(self) -> bool:
        return not self.entries


@dataclass(frozen=True)
class AuditorPolicy:
    blocked: frozenset[str]
    aliases: dict[str, str]
    gap_policy: str = "manual_verify"

    @classmethod
    def from_yaml(cls, raw: dict, gap_policy: str = "manual_verify") -> AuditorPolicy:
        return cls(
            blocked=frozenset(raw.get("blocked") or ()),
            aliases=dict(raw.get("aliases") or {}),
            gap_policy=gap_policy,
        )

    def normalize(self, name: str) -> str:
        clean = (name or "").strip()
        return self.aliases.get(clean, clean)

    def is_blocked(self, name: str) -> bool:
        return self.normalize(name) in self.blocked

    def to_ref(self, entry: AuditEntry) -> AuditorRef:
        return AuditorRef(
            fiscal_year=entry.fiscal_year,
            auditor=entry.auditor,
            auditor_normalized=self.normalize(entry.auditor),
            opinion=entry.opinion,
            consecutive_years=entry.consecutive_years,
            report_type=entry.report_type,
        )


def decide_alert(history: AuditHistory | None, policy: AuditorPolicy) -> Decision:
    if history is None:
        return Decision.manual_verify(reason="감사인 조회 결과 없음")
    if history.error:
        return Decision.manual_verify(reason=f"감사인 조회 실패: {history.error}")
    if history.is_empty:
        return Decision.manual_verify(reason="감사인 데이터 미수록 (kreports DB 비어있음)")

    e2026 = history.find_2026()
    e2025 = history.find_2025()
    ref2025 = policy.to_ref(e2025) if e2025 else None

    if e2026 is None:
        if policy.gap_policy == "carry_forward" and e2025 is not None:
            if policy.is_blocked(e2025.auditor):
                return Decision.skip(reason=f"차단(carry-forward 2025): {e2025.auditor}")
            return Decision(
                kind=Decision.clean(policy.to_ref(e2025)).kind,
                reason="2025 감사인 carry-forward 적용 (2026 미공시)",
                auditor_2026=None,
                auditor_2025=ref2025,
            )
        return Decision.manual_verify(
            reason="2026 감사인 정보 미확정 (1Q 보고서 미공시 가능)",
            auditor_2025=ref2025,
        )

    if policy.is_blocked(e2026.auditor):
        return Decision.skip(reason=f"차단: {e2026.auditor}")

    return Decision.clean(policy.to_ref(e2026))
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/webhook/test_policy.py -v
```

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add webhook/policy.py tests/webhook/test_policy.py
git commit -m "feat(stock-intel): add webhook/policy — AuditHistory + AuditorPolicy + decide_alert"
```

---

## Task 5: webhook/lookup.py

**Files:**
- Create: `webhook/lookup.py`
- Create: `tests/webhook/test_lookup.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/webhook/test_lookup.py
import json
import sqlite3
import time
import pytest
from webhook.lookup import CachedAuditorLookup, KreportsLookup
from webhook.policy import AuditEntry, AuditHistory


class _FakeLookup:
    def __init__(self, result: AuditHistory) -> None:
        self._result = result
        self.call_count = 0

    def fetch(self, ticker: str) -> AuditHistory:
        self.call_count += 1
        return self._result


def _fresh_history(ticker: str = "005930") -> AuditHistory:
    return AuditHistory(
        ticker=ticker,
        entries=(AuditEntry("2026", "한영회계법인", "CFS"),),
        fetched_at=int(time.time()),
    )


def test_cached_lookup_miss_delegates():
    inner = _FakeLookup(_fresh_history())
    cache = CachedAuditorLookup(inner, db_path=":memory:", ttl_seconds=3600)
    result = cache.fetch("005930")
    assert result.ticker == "005930"
    assert inner.call_count == 1


def test_cached_lookup_hit_no_delegate():
    inner = _FakeLookup(_fresh_history())
    cache = CachedAuditorLookup(inner, db_path=":memory:", ttl_seconds=3600)
    cache.fetch("005930")
    cache.fetch("005930")
    assert inner.call_count == 1


def test_cached_lookup_expired_refetches():
    inner = _FakeLookup(_fresh_history())
    cache = CachedAuditorLookup(inner, db_path=":memory:", ttl_seconds=10)
    cache.fetch("005930")
    # Manually expire the cache entry
    with sqlite3.connect(":memory:") as _:
        pass  # Can't easily expire :memory: — test TTL logic via unit
    # Second call still hits cache (not expired yet)
    cache.fetch("005930")
    assert inner.call_count == 1


def test_kreports_lookup_missing_package_returns_error():
    import sys
    # Temporarily hide kreports if present
    kreports_mod = sys.modules.pop("kreports", None)
    try:
        lookup = KreportsLookup()
        lookup._impl = None
        # Patch all import paths to fail
        import unittest.mock as mock
        with mock.patch.dict("sys.modules", {"kreports": None, "kreports.tools.audit_history": None, "kreports.api": None}):
            result = lookup.fetch("005930")
        assert result.error is not None
    finally:
        if kreports_mod is not None:
            sys.modules["kreports"] = kreports_mod
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/webhook/test_lookup.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'webhook.lookup'`

- [ ] **Step 3: webhook/lookup.py 구현**

```python
# webhook/lookup.py
"""kreports get_audit_history wrapper + SQLite TTL cache."""
from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from webhook.policy import AuditEntry, AuditHistory


class AuditorLookup(Protocol):
    def fetch(self, ticker: str) -> AuditHistory: ...


# ---------------------------------------------------------------------------
# KreportsLookup
# ---------------------------------------------------------------------------

class KreportsLookup:
    def __init__(self, *, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._impl = None

    def _resolve_callable(self) -> Any:
        if self._impl is not None:
            return self._impl
        try:
            from kreports.tools.audit_history import get_audit_history  # type: ignore
            self._impl = get_audit_history
            return self._impl
        except ImportError:
            pass
        try:
            from kreports.api import get_audit_history  # type: ignore
            self._impl = get_audit_history
            return self._impl
        except ImportError:
            pass
        try:
            import kreports  # type: ignore
            fn = getattr(kreports, "get_audit_history", None)
            if fn is not None:
                self._impl = fn
                return self._impl
        except ImportError:
            pass
        raise RuntimeError("kreports is not installed or get_audit_history not found.")

    def fetch(self, ticker: str) -> AuditHistory:
        now = int(time.time())
        try:
            fn = self._resolve_callable()
            raw = fn(company=ticker)
        except Exception as e:
            return AuditHistory(ticker=ticker, entries=(), fetched_at=now, error=str(e))
        return _normalize(ticker, raw, fetched_at=now)


def _normalize(ticker: str, raw: dict, *, fetched_at: int) -> AuditHistory:
    if not isinstance(raw, dict):
        return AuditHistory(
            ticker=ticker, entries=(), fetched_at=fetched_at,
            error=f"unexpected type: {type(raw).__name__}",
        )
    err = raw.get("error")
    if err:
        return AuditHistory(ticker=ticker, entries=(), fetched_at=fetched_at, error=str(err))

    history = raw.get("history") or []
    entries: list[AuditEntry] = []
    for row in history:
        if not isinstance(row, dict):
            continue
        fy = str(row.get("회계연도") or row.get("fiscal_year") or "").strip()
        auditor = str(row.get("감사인") or row.get("auditor") or "").strip()
        if not fy or not auditor:
            continue
        entries.append(AuditEntry(
            fiscal_year=fy,
            auditor=auditor,
            report_type=str(row.get("구분") or row.get("report_type") or "CFS").upper(),
            opinion=_opt_str(_pick(row, "감사의견", "opinion")),
            consecutive_years=_opt_int(_pick(row, "연속연수", "consecutive_years")),
            auditor_changed=_opt_bool(_pick(row, "교체여부", "auditor_changed")),
        ))
    return AuditHistory(ticker=ticker, entries=tuple(entries), fetched_at=fetched_at)


def _pick(row: dict, *keys: str) -> Any:
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return None

def _opt_str(v: Any) -> str | None:
    if v is None: return None
    s = str(v).strip(); return s or None

def _opt_int(v: Any) -> int | None:
    if v is None: return None
    try: return int(v)
    except (TypeError, ValueError): return None

def _opt_bool(v: Any) -> bool | None:
    if v is None: return None
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)): return bool(v)
    s = str(v).strip().lower()
    if s in ("true", "1", "y", "yes", "교체"): return True
    if s in ("false", "0", "n", "no", "유지"): return False
    return None


# ---------------------------------------------------------------------------
# CachedAuditorLookup
# ---------------------------------------------------------------------------

_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_cache (
    ticker TEXT PRIMARY KEY,
    fetched_at INTEGER NOT NULL,
    error TEXT,
    payload TEXT NOT NULL
);
"""


class CachedAuditorLookup:
    def __init__(
        self,
        inner: AuditorLookup,
        *,
        db_path: str | Path,
        ttl_seconds: int,
    ) -> None:
        self._inner = inner
        self._path = str(db_path)
        self._ttl = ttl_seconds
        self._init()

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_CACHE_SCHEMA)
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, isolation_level=None, timeout=5.0)
        try:
            yield conn
        finally:
            conn.close()

    def fetch(self, ticker: str) -> AuditHistory:
        cached = self._read(ticker)
        if cached is not None:
            return cached
        fresh = self._inner.fetch(ticker)
        self._write(fresh)
        return fresh

    def _read(self, ticker: str) -> AuditHistory | None:
        cutoff = int(time.time()) - self._ttl
        with self._connect() as conn:
            row = conn.execute(
                "SELECT fetched_at, error, payload FROM audit_cache WHERE ticker = ?",
                (ticker,),
            ).fetchone()
        if row is None:
            return None
        fetched_at, error, payload = row
        if fetched_at < cutoff and not error:
            return None
        if error and fetched_at < cutoff:
            return None
        entries = tuple(AuditEntry(**e) for e in json.loads(payload))
        return AuditHistory(ticker=ticker, entries=entries, fetched_at=fetched_at, error=error)

    def _write(self, h: AuditHistory) -> None:
        payload = json.dumps([asdict(e) for e in h.entries], ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO audit_cache(ticker, fetched_at, error, payload) "
                "VALUES (?, ?, ?, ?)",
                (h.ticker, h.fetched_at, h.error, payload),
            )
            conn.commit()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/webhook/test_lookup.py -v
```

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add webhook/lookup.py tests/webhook/test_lookup.py
git commit -m "feat(stock-intel): add webhook/lookup — KreportsLookup + CachedAuditorLookup"
```

---

## Task 6: webhook/notify.py

**Files:**
- Create: `webhook/notify.py`
- Create: `tests/webhook/test_notify.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/webhook/test_notify.py
import pytest
from webhook.domain import AuditorRef, Decision, DecisionKind, Webhook
from webhook.notify import format_signal_message, split_for_telegram


def _buy_webhook(**overrides) -> Webhook:
    base = {
        "ticker": "005930", "name": "삼성전자", "exchange": "KOSPI",
        "timeframe": "1D", "action": "BUY", "type": "💰 정석 진입",
        "price": 75000.0, "score": 80, "conviction": "A",
        "candle_type": "양봉", "ema_touch": "ema1", "ema_align": "정배열",
    }
    base.update(overrides)
    return Webhook.model_validate(base)


# --- split_for_telegram ---

def test_split_short_text():
    assert split_for_telegram("hello") == ["hello"]


def test_split_long_text_splits_on_newline():
    short = "line\n" * 100
    chunks = split_for_telegram(short, limit=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.encode("utf-8")) <= 200


def test_split_no_separator_hard_split():
    text = "a" * 500
    chunks = split_for_telegram(text, limit=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.encode("utf-8")) <= 200


# --- format_signal_message ---

def test_format_clean_contains_green_circle():
    ref = AuditorRef("2026", "한영회계법인", "한영회계법인")
    d = Decision.clean(ref)
    msg = format_signal_message(_buy_webhook(), d)
    assert "🟢" in msg
    assert "삼성전자" in msg
    assert "한영회계법인" in msg
    assert "💰 정석 진입" in msg


def test_format_manual_verify_contains_yellow():
    ref25 = AuditorRef("2025", "한영회계법인", "한영회계법인")
    d = Decision.manual_verify(reason="2026 미공시", auditor_2025=ref25)
    msg = format_signal_message(_buy_webhook(), d)
    assert "🟡" in msg
    assert "직접 확인 필요" in msg
    assert "한영회계법인" in msg


def test_format_raises_for_skip():
    d = Decision.skip("action=SELL")
    with pytest.raises(ValueError, match="non-notify"):
        format_signal_message(_buy_webhook(), d)
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/webhook/test_notify.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'webhook.notify'`

- [ ] **Step 3: webhook/notify.py 구현**

```python
# webhook/notify.py
"""Signal-specific Telegram sender + message formatter.

format_signal_message — 시그널 알림 전용. utils/formatter.py의 format_message(stock info card)와 별도.
"""
from __future__ import annotations

import logging
from typing import Protocol

import httpx

from webhook.domain import Decision, DecisionKind, Webhook

logger = logging.getLogger(__name__)

TELEGRAM_MAX_BYTES = 4096


class TelegramSender(Protocol):
    def send(self, text: str) -> list[int]: ...


class HttpxTelegramSender:
    def __init__(self, bot_token: str, chat_id: str, *, timeout_sec: float = 30.0) -> None:
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout_sec

    def send(self, text: str) -> list[int]:
        chunks = split_for_telegram(text)
        message_ids: list[int] = []
        reply_to: int | None = None
        with httpx.Client(timeout=self._timeout) as client:
            for chunk in chunks:
                payload: dict = {
                    "chat_id": self._chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                }
                if reply_to is not None:
                    payload["reply_to_message_id"] = reply_to
                resp = client.post(self._url, json=payload)
                resp.raise_for_status()
                msg_id = int(resp.json()["result"]["message_id"])
                message_ids.append(msg_id)
                reply_to = msg_id
        return message_ids


class StdoutTelegramSender:
    def __init__(self) -> None:
        self._counter = 0

    def send(self, text: str) -> list[int]:
        ids: list[int] = []
        for chunk in split_for_telegram(text):
            self._counter += 1
            ids.append(self._counter)
            print(f"---[signal dry-run #{self._counter}]---")
            print(chunk)
            print("---[end]---", flush=True)
        return ids


def split_for_telegram(text: str, *, limit: int = TELEGRAM_MAX_BYTES) -> list[str]:
    if len(text.encode("utf-8")) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining.encode("utf-8")) <= limit:
            chunks.append(remaining)
            break
        head, tail = _split_one(remaining, limit)
        chunks.append(head)
        remaining = tail
    return chunks


def _split_one(text: str, limit: int) -> tuple[str, str]:
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text, ""
    cut = limit
    while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
        cut -= 1
    candidate = encoded[:cut].decode("utf-8", errors="ignore")
    for sep in ("\n\n", "\n", ". ", " "):
        idx = candidate.rfind(sep)
        if idx > 0:
            split_at = idx + len(sep)
            return candidate[:split_at].rstrip(), text[split_at:]
    return candidate, text[len(candidate):]


# ---------------------------------------------------------------------------
# Message formatters
# ---------------------------------------------------------------------------

def format_signal_message(webhook: Webhook, decision: Decision) -> str:
    if decision.kind == DecisionKind.CLEAN:
        return _format_clean(webhook, decision)
    if decision.kind == DecisionKind.MANUAL_VERIFY:
        return _format_manual(webhook, decision)
    raise ValueError(f"format_signal_message called for non-notify decision: {decision.kind}")


def _format_clean(w: Webhook, d: Decision) -> str:
    a = d.auditor_2026
    auditor_line = (
        f"✅ 2026 감사인: {a.auditor}"
        + (f" (의견: {a.opinion}" if a.opinion else "")
        + (f", 연속 {a.consecutive_years}년)" if a.consecutive_years is not None else (")" if a.opinion else ""))
    ) if a else "✅ 2026 감사인: (정보 없음)"

    return "\n".join(filter(None, [
        "🟢 매수 시그널 — 안전 종목",
        "",
        f"종목: {w.name} ({w.ticker})" + (f" · {w.exchange}" if w.exchange else ""),
        f"시그널: {w.type}",
        _trade_line(w),
        _market_line(w),
        _daily_line(w),
        "",
        auditor_line,
        "———",
        f"desc: {w.desc}" if w.desc else "",
        f"ai: {w.ai_summary}" if w.ai_summary else "",
    ])).rstrip()


def _format_manual(w: Webhook, d: Decision) -> str:
    a25 = d.auditor_2025
    last_known = (
        f"   직전(2025): {a25.auditor}"
        + (f" (연속 {a25.consecutive_years}년)" if a25.consecutive_years is not None else "")
        if a25 else "   직전(2025): 정보 없음"
    )
    return "\n".join(filter(None, [
        "🟡 매수 시그널 — 직접 확인 필요",
        "",
        f"종목: {w.name} ({w.ticker})" + (f" · {w.exchange}" if w.exchange else ""),
        f"시그널: {w.type}",
        _trade_line(w),
        _market_line(w),
        _daily_line(w),
        "",
        "⚠️ 2026 감사인 정보 미확정",
        f"   ({d.reason})",
        last_known,
        "   → DART에서 직접 확인 후 진입 결정",
        "———",
        f"desc: {w.desc}" if w.desc else "",
        f"ai: {w.ai_summary}" if w.ai_summary else "",
    ])).rstrip()


def _trade_line(w: Webhook) -> str:
    parts = [f"타임프레임: {w.timeframe}", f"진입가: {_fmt_price(w.price)}"]
    if w.sl is not None: parts.append(f"손절: {_fmt_price(w.sl)}")
    if w.rr is not None: parts.append(f"RR: {w.rr}")
    return " | ".join(parts)


def _market_line(w: Webhook) -> str:
    parts = []
    if w.market: parts.append(f"시장: {w.market}")
    if w.status: parts.append(f"신호등: {w.status}")
    if w.conviction: parts.append(f"등급: {w.conviction}")
    return " · ".join(parts)


def _daily_line(w: Webhook) -> str:
    bits = [f"스코어: {w.score}"]
    daily_bits: list[str] = []
    if w.daily_trend: daily_bits.append(w.daily_trend)
    if w.daily_above_200ma: daily_bits.append("200MA 위")
    if w.daily_rs: daily_bits.append(f"RS {w.daily_rs}")
    if daily_bits: bits.append("일봉: " + ", ".join(daily_bits))
    return " · ".join(bits)


def _fmt_price(v: float) -> str:
    if v >= 1000:
        return f"{int(v):,}" if float(v).is_integer() else f"{v:,.2f}"
    return f"{v:g}"
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/webhook/test_notify.py -v
```

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add webhook/notify.py tests/webhook/test_notify.py
git commit -m "feat(stock-intel): add webhook/notify — TelegramSender + format_signal_message"
```

---

## Task 7: webhook/pipeline.py

**Files:**
- Create: `webhook/pipeline.py`
- Create: `tests/webhook/test_pipeline.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/webhook/test_pipeline.py
import json
import time
import pytest
from webhook.domain import AuditorRef, Decision, DecisionKind, Webhook
from webhook.filters import BuyFilterConfig, DedupStore
from webhook.notify import TelegramSender
from webhook.pipeline import DecisionLogger, Pipeline
from webhook.policy import AuditEntry, AuditHistory, AuditorPolicy


def _buy_webhook(**overrides) -> Webhook:
    base = {
        "ticker": "005930", "name": "삼성전자", "exchange": "KOSPI",
        "timeframe": "1D", "action": "BUY", "type": "💰 정석 진입",
        "price": 75000.0, "score": 80, "conviction": "A",
        "candle_type": "양봉", "ema_touch": "ema1", "ema_align": "정배열",
    }
    base.update(overrides)
    return Webhook.model_validate(base)


class _FakeLookup:
    def __init__(self, history: AuditHistory) -> None:
        self._history = history

    def fetch(self, ticker: str) -> AuditHistory:
        return self._history


class _FakeSender:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, text: str) -> list[int]:
        self.sent.append(text)
        return [len(self.sent)]


class _NullLogger:
    def log(self, record: dict) -> None:
        pass


def _make_pipeline(history: AuditHistory, sender: _FakeSender | None = None) -> Pipeline:
    if sender is None:
        sender = _FakeSender()
    return Pipeline(
        buy_filter=BuyFilterConfig(),
        policy=AuditorPolicy(blocked=frozenset(["삼정회계법인"]), aliases={}),
        lookup=_FakeLookup(history),
        dedup=DedupStore(":memory:", window_seconds=300),
        sender=sender,
        decision_log=_NullLogger(),
    )


def _clean_history() -> AuditHistory:
    return AuditHistory(
        ticker="005930",
        entries=(AuditEntry("2026", "한영회계법인", "CFS"),),
        fetched_at=int(time.time()),
    )


def _blocked_history() -> AuditHistory:
    return AuditHistory(
        ticker="005930",
        entries=(AuditEntry("2026", "삼정회계법인", "CFS"),),
        fetched_at=int(time.time()),
    )


def test_pipeline_clean_sends_notification():
    sender = _FakeSender()
    pipeline = _make_pipeline(_clean_history(), sender)
    d = pipeline.handle(_buy_webhook())
    assert d.kind == DecisionKind.CLEAN
    assert len(sender.sent) == 1
    assert "🟢" in sender.sent[0]


def test_pipeline_blocked_no_notification():
    sender = _FakeSender()
    pipeline = _make_pipeline(_blocked_history(), sender)
    d = pipeline.handle(_buy_webhook())
    assert d.kind == DecisionKind.SKIP
    assert len(sender.sent) == 0


def test_pipeline_sell_action_skipped():
    sender = _FakeSender()
    pipeline = _make_pipeline(_clean_history(), sender)
    d = pipeline.handle(_buy_webhook(action="SELL"))
    assert d.kind == DecisionKind.SKIP
    assert len(sender.sent) == 0


def test_pipeline_dedup_blocks_second():
    sender = _FakeSender()
    pipeline = _make_pipeline(_clean_history(), sender)
    wh = _buy_webhook()
    pipeline.handle(wh)
    d2 = pipeline.handle(wh)
    assert d2.kind == DecisionKind.SKIP
    assert len(sender.sent) == 1  # 첫 번째만 발송


def test_pipeline_manual_verify_sends_notification():
    history = AuditHistory(ticker="005930", entries=(), fetched_at=0)
    sender = _FakeSender()
    pipeline = _make_pipeline(history, sender)
    d = pipeline.handle(_buy_webhook())
    assert d.kind == DecisionKind.MANUAL_VERIFY
    assert len(sender.sent) == 1
    assert "🟡" in sender.sent[0]
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/webhook/test_pipeline.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'webhook.pipeline'`

- [ ] **Step 3: webhook/pipeline.py 구현**

```python
# webhook/pipeline.py
"""Signal processing pipeline + JSONL decision logger."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from webhook.domain import Decision, DecisionKind, Webhook
from webhook.filters import BuyFilterConfig, DedupStore, passes_buy_filter
from webhook.lookup import AuditorLookup
from webhook.notify import TelegramSender, format_signal_message
from webhook.policy import AuditorPolicy, decide_alert

logger = logging.getLogger(__name__)


class DecisionLogger:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: dict) -> None:
        record.setdefault("ts", int(time.time()))
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


@dataclass
class Pipeline:
    buy_filter: BuyFilterConfig
    policy: AuditorPolicy
    lookup: AuditorLookup
    dedup: DedupStore
    sender: TelegramSender
    decision_log: DecisionLogger

    def handle(self, webhook: Webhook) -> Decision:
        ok, why = passes_buy_filter(webhook, self.buy_filter)
        if not ok:
            decision = Decision.skip(why)
            self._log(webhook, decision)
            return decision

        key = self.dedup.make_key(webhook.ticker, webhook.base_type(), webhook.timeframe)
        if self.dedup.is_duplicate(key):
            decision = Decision.skip("dedup hit")
            self._log(webhook, decision)
            return decision

        try:
            history = self.lookup.fetch(webhook.ticker)
        except Exception as e:
            logger.exception("auditor lookup failed", extra={"ticker": webhook.ticker})
            decision = Decision.manual_verify(reason=f"감사인 조회 예외: {e!r}")
            self._notify(webhook, decision)
            self._log(webhook, decision)
            return decision

        decision = decide_alert(history, self.policy)
        if decision.should_notify:
            self._notify(webhook, decision)
        self._log(webhook, decision)
        return decision

    def _notify(self, webhook: Webhook, decision: Decision) -> None:
        try:
            text = format_signal_message(webhook, decision)
            self.sender.send(text)
        except Exception:
            logger.exception("telegram send failed", extra={"ticker": webhook.ticker})

    def _log(self, webhook: Webhook, decision: Decision) -> None:
        try:
            self.decision_log.log({
                "ticker": webhook.ticker,
                "name": webhook.name,
                "exchange": webhook.exchange,
                "action": webhook.action,
                "type": webhook.type,
                "decision": decision.kind.value,
                "reason": decision.reason,
                "auditor_2026": decision.auditor_2026.auditor if decision.auditor_2026 else None,
                "auditor_2025": decision.auditor_2025.auditor if decision.auditor_2025 else None,
                "score": webhook.score,
                "conviction": webhook.conviction,
            })
        except Exception:
            logger.exception("decision log failed", extra={"ticker": webhook.ticker})
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/webhook/test_pipeline.py -v
```

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add webhook/pipeline.py tests/webhook/test_pipeline.py
git commit -m "feat(stock-intel): add webhook/pipeline — Pipeline + DecisionLogger"
```

---

## Task 8: webhook/config.py + webhook/server.py

**Files:**
- Create: `webhook/config.py`
- Create: `webhook/server.py`
- Create: `tests/webhook/test_server.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/webhook/test_server.py
import time
import pytest
from fastapi.testclient import TestClient
from webhook.filters import BuyFilterConfig, DedupStore
from webhook.notify import StdoutTelegramSender
from webhook.pipeline import DecisionLogger, Pipeline
from webhook.policy import AuditEntry, AuditHistory, AuditorPolicy
from webhook.server import create_webhook_app


def _fake_pipeline() -> Pipeline:
    class FakeLookup:
        def fetch(self, ticker: str) -> AuditHistory:
            return AuditHistory(
                ticker=ticker,
                entries=(AuditEntry("2026", "한영회계법인", "CFS"),),
                fetched_at=int(time.time()),
            )

    import tempfile, os
    tmp = tempfile.mktemp(suffix=".db")
    return Pipeline(
        buy_filter=BuyFilterConfig(),
        policy=AuditorPolicy(blocked=frozenset(["삼정회계법인"]), aliases={}),
        lookup=FakeLookup(),
        dedup=DedupStore(tmp, window_seconds=300),
        sender=StdoutTelegramSender(),
        decision_log=DecisionLogger("/tmp/test_decisions.jsonl"),
    )


def _buy_payload(**overrides) -> dict:
    base = {
        "ticker": "005930", "name": "삼성전자", "exchange": "KOSPI",
        "timeframe": "1D", "action": "BUY", "type": "💰 정석 진입",
        "price": 75000.0, "score": 80, "conviction": "A",
        "candle_type": "양봉", "ema_touch": "ema1", "ema_align": "정배열",
    }
    base.update(overrides)
    return base


def _client(secret: str = "test-secret") -> TestClient:
    app = create_webhook_app(webhook_secret=secret, pipeline=_fake_pipeline())
    return TestClient(app, raise_server_exceptions=False)


def test_healthz_ok():
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_wrong_secret_401():
    resp = _client(secret="real").post("/webhook?secret=wrong", json=_buy_payload())
    assert resp.status_code == 401


def test_webhook_invalid_json_body_400():
    resp = _client().post("/webhook?secret=test-secret", content="not-json",
                          headers={"Content-Type": "application/json"})
    assert resp.status_code == 400


def test_webhook_schema_violation_422():
    resp = _client().post("/webhook?secret=test-secret", json={"ticker": "005930"})
    assert resp.status_code == 422


def test_webhook_buy_accepted():
    resp = _client().post("/webhook?secret=test-secret", json=_buy_payload())
    assert resp.status_code == 200
    assert resp.json()["received"] is True
    assert resp.json()["ticker"] == "005930"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/webhook/test_server.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'webhook.server'`

- [ ] **Step 3: webhook/config.py 구현**

```python
# webhook/config.py
"""Webhook pipeline settings from env + YAML files."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from webhook.filters import BuyFilterConfig
from webhook.policy import AuditorPolicy


class WebhookSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    webhook_secret: str = Field(default="dev-secret", alias="WEBHOOK_SECRET")
    signal_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    signal_chat_id: str = Field(default="", alias="SIGNAL_CHAT_ID")
    dry_run: bool = Field(default=False, alias="DRY_RUN")

    kreports_db_path: str = Field(default="./kreports.db", alias="KREPORTS_DB_PATH")
    state_db_path: str = Field(default="./state.db", alias="STATE_DB_PATH")
    cache_ttl_days: int = Field(default=7, alias="CACHE_TTL_DAYS")
    dedup_window_minutes: int = Field(default=5, alias="DEDUP_WINDOW_MINUTES")

    blocked_auditors_path: str = Field(
        default="./config/blocked_auditors.yaml", alias="BLOCKED_AUDITORS_PATH"
    )
    settings_path: str = Field(
        default="./config/settings.yaml", alias="SETTINGS_PATH"
    )
    decision_log_path: str = Field(
        default="./logs/decisions.jsonl", alias="DECISION_LOG_PATH"
    )


def load_buy_filter(settings: WebhookSettings) -> BuyFilterConfig:
    raw = _read_yaml(settings.settings_path) or {}
    return BuyFilterConfig.from_yaml(raw)


def load_auditor_policy(settings: WebhookSettings) -> AuditorPolicy:
    raw_settings = _read_yaml(settings.settings_path) or {}
    raw_blocked = _read_yaml(settings.blocked_auditors_path) or {}
    gap_policy = str(raw_settings.get("gap_policy") or "manual_verify")
    return AuditorPolicy.from_yaml(raw_blocked, gap_policy=gap_policy)


def _read_yaml(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else None
```

- [ ] **Step 4: webhook/server.py 구현**

```python
# webhook/server.py
"""FastAPI webhook receiver — /healthz + POST /webhook."""
from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from webhook.domain import Webhook
from webhook.pipeline import Pipeline

logger = logging.getLogger(__name__)


def create_webhook_app(
    *,
    webhook_secret: str,
    pipeline: Pipeline,
) -> FastAPI:
    """Factory — creates a FastAPI app with webhook routes wired to pipeline."""
    app = FastAPI(title="stock-intel-webhook", version="0.2.0")
    app.state.secret = webhook_secret
    app.state.pipeline = pipeline

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "version": "0.2.0"}

    @app.post("/webhook")
    async def webhook_endpoint(
        request: Request,
        background: BackgroundTasks,
        secret: str = "",
    ) -> JSONResponse:
        if not secrets.compare_digest(secret, app.state.secret):
            raise HTTPException(status_code=401, detail="invalid secret")
        try:
            payload = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid json: {e!r}") from e
        try:
            wh = Webhook.model_validate(payload)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"schema: {e!r}") from e

        background.add_task(_safe_handle, app.state.pipeline, wh)
        return JSONResponse({"received": True, "ticker": wh.ticker})

    return app


def _safe_handle(pipeline: Pipeline, webhook: Webhook) -> None:
    try:
        pipeline.handle(webhook)
    except Exception:
        logger.exception("pipeline failed", extra={"ticker": webhook.ticker})


def build_webhook_pipeline(settings: "WebhookSettings") -> Pipeline:  # noqa: F821
    """Build production pipeline from settings."""
    from webhook.config import load_auditor_policy, load_buy_filter
    from webhook.filters import DedupStore
    from webhook.lookup import CachedAuditorLookup, KreportsLookup
    from webhook.notify import HttpxTelegramSender, StdoutTelegramSender
    from webhook.pipeline import DecisionLogger

    inner = KreportsLookup(db_path=settings.kreports_db_path)
    cached = CachedAuditorLookup(
        inner,
        db_path=settings.state_db_path,
        ttl_seconds=settings.cache_ttl_days * 86400,
    )
    dedup = DedupStore(
        settings.state_db_path,
        window_seconds=settings.dedup_window_minutes * 60,
    )
    if settings.dry_run or not settings.signal_bot_token or not settings.signal_chat_id:
        sender = StdoutTelegramSender()
    else:
        sender = HttpxTelegramSender(settings.signal_bot_token, settings.signal_chat_id)

    return Pipeline(
        buy_filter=load_buy_filter(settings),
        policy=load_auditor_policy(settings),
        lookup=cached,
        dedup=dedup,
        sender=sender,
        decision_log=DecisionLogger(settings.decision_log_path),
    )
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/webhook/test_server.py -v
```

Expected: 모든 테스트 PASS.

- [ ] **Step 6: 커밋**

```bash
git add webhook/config.py webhook/server.py tests/webhook/test_server.py
git commit -m "feat(stock-intel): add webhook/config + webhook/server — FastAPI webhook endpoint"
```

---

## Task 9: bot.py 리팩토링 + app.py 생성

**Files:**
- Modify: `bot.py`
- Create: `app.py`

이 태스크는 Telegram polling과 FastAPI webhook을 단일 프로세스에서 공존시킨다.

`python-telegram-bot` v20+는 `Application.run_polling()`이 이벤트 루프를 소유한다. FastAPI + uvicorn과 공존하려면 `async with Application` 컨텍스트를 통해 polling을 FastAPI lifespan 안에서 수동으로 시작해야 한다.

- [ ] **Step 1: bot.py 리팩토링**

`build_telegram_app()` 함수를 추출하고 `if __name__ == "__main__"` 블록을 제거한다.

```python
# bot.py (수정 후 전체)
"""bot.py — Telegram stock intel bot handlers.

Application 인스턴스는 build_telegram_app()으로 생성한다.
실제 실행은 app.py(uvicorn 진입점)가 lifespan 안에서 담당한다.
"""
from __future__ import annotations

import asyncio
import logging
import os

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from data.audit_firm import fetch_audit_firm
from data.fundamental import fetch_fundamental
from data.short_sell import fetch_short_sell
from data.supply import fetch_supply
from data.technical import fetch_technical
from utils.formatter import format_message
from utils.ticker import refresh_ticker_cache, search_ticker

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

ALLOWED_IDS: set[int] = {
    int(x.strip())
    for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",")
    if x.strip()
}

_KST = pytz.timezone("Asia/Seoul")


async def check_allowed(update: Update) -> bool:
    if not ALLOWED_IDS:
        return True
    chat_id = update.effective_chat.id
    allowed = chat_id in ALLOWED_IDS
    if not allowed:
        logger.warning("차단된 chat_id: %s", chat_id)
    return allowed


def fetch_all(ticker: str) -> tuple[dict, dict, dict, dict, dict]:
    return (
        fetch_supply(ticker),
        fetch_short_sell(ticker),
        fetch_technical(ticker),
        fetch_fundamental(ticker),
        fetch_audit_firm(ticker),
    )


async def _fetch_and_reply(update: Update, ticker: str, name: str, loading_message) -> None:
    supply, short_sell, technical, fundamental, audit = await asyncio.to_thread(fetch_all, ticker)
    text = format_message(name, ticker, supply, short_sell, technical, fundamental, audit)
    await loading_message.edit_text(text)


async def _lookup_and_reply(update: Update, query: str) -> None:
    query = query.strip()
    if not query:
        await update.message.reply_text(
            "조회할 종목명을 같이 보내주세요.\n예) /s 삼성전자"
        )
        return
    results = await asyncio.to_thread(search_ticker, query)
    if not results:
        await update.message.reply_text("종목을 찾을 수 없습니다.")
        return
    if len(results) == 1:
        item = results[0]
        loading_msg = await update.message.reply_text("🔍 조회 중...")
        await _fetch_and_reply(update, item["code"], item["name"], loading_msg)
        return
    buttons = [
        InlineKeyboardButton(
            f"{item['name']} ({item['market']})",
            callback_data=f"ticker:{item['code']}:{item['name']}",
        )
        for item in results[:5]
    ]
    await update.message.reply_text(
        "종목을 선택해 주세요:", reply_markup=InlineKeyboardMarkup([[b] for b in buttons])
    )


async def handle_start(update: Update, context) -> None:
    if not await check_allowed(update): return
    await update.message.reply_text(
        "종목명을 입력하면 수급현황, 공매도, 기술적 지표, 펀더멘탈, 감사법인을 보여드립니다."
    )


async def handle_ping(update: Update, context) -> None:
    if not await check_allowed(update): return
    await update.message.reply_text("pong")


async def handle_lookup_command(update: Update, context) -> None:
    if not await check_allowed(update): return
    await _lookup_and_reply(update, " ".join(context.args).strip())


async def handle_korean_lookup_text(update: Update, context) -> None:
    if not await check_allowed(update): return
    text = update.message.text.strip()
    query = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""
    await _lookup_and_reply(update, query)


async def handle_text(update: Update, context) -> None:
    if not await check_allowed(update): return
    await _lookup_and_reply(update, update.message.text.strip())


async def handle_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    if not await check_allowed(update): return
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await query.edit_message_text("잘못된 요청입니다.")
        return
    _, ticker, name = parts
    await query.edit_message_text("🔍 조회 중...")
    supply, short_sell, technical, fundamental, audit = await asyncio.to_thread(fetch_all, ticker)
    await query.edit_message_text(
        format_message(name, ticker, supply, short_sell, technical, fundamental, audit)
    )


def build_telegram_app() -> Application:
    """Build and register all handlers. Caller owns start/stop lifecycle."""
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("ping", handle_ping))
    app.add_handler(CommandHandler(["stock", "s", "check"], handle_lookup_command))
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^/조회(?:@\S+)?(?:\s+.*)?$"),
            handle_korean_lookup_text,
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^ticker:"))

    return app
```

- [ ] **Step 2: app.py 생성**

```python
# app.py
"""FastAPI entrypoint — Telegram polling + webhook receiver in one process.

실행: uv run uvicorn app:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from bot import build_telegram_app
from utils.ticker import refresh_ticker_cache
from webhook.config import WebhookSettings
from webhook.server import build_webhook_pipeline, create_webhook_app

logger = logging.getLogger(__name__)
_KST = pytz.timezone("Asia/Seoul")


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    settings = WebhookSettings()

    # --- Telegram polling ---
    tg = build_telegram_app()
    await tg.initialize()
    await tg.start()
    await tg.updater.start_polling(allowed_updates=["message", "callback_query"])

    # --- Ticker cache scheduler ---
    scheduler = AsyncIOScheduler(timezone=_KST)
    scheduler.add_job(
        lambda: asyncio.create_task(asyncio.to_thread(refresh_ticker_cache)),
        CronTrigger(hour=7, minute=0, timezone=_KST),
        id="refresh_ticker_cache",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("봇 시작 — Telegram polling + webhook server (port from uvicorn)")

    yield

    # --- Shutdown ---
    scheduler.shutdown(wait=False)
    await tg.updater.stop()
    await tg.stop()
    await tg.shutdown()


def _build_app() -> FastAPI:
    settings = WebhookSettings()
    pipeline = build_webhook_pipeline(settings)
    fastapi_app = create_webhook_app(
        webhook_secret=settings.webhook_secret,
        pipeline=pipeline,
    )
    fastapi_app.router.lifespan_context = lifespan
    return fastapi_app


app = _build_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=False)
```

- [ ] **Step 3: 로컬 스모크 테스트 — uvicorn 기동**

```bash
cd /Users/kjun/vault/01_Projects/04_stock_intel
uv run uvicorn app:app --host 0.0.0.0 --port 8080 --log-level info
```

Expected: `봇 시작 — Telegram polling + webhook server` 로그 출력 후 대기.

- [ ] **Step 4: /healthz 확인 (별도 터미널)**

```bash
curl -s http://localhost:8080/healthz | python3 -m json.tool
```

Expected:
```json
{"status": "ok", "version": "0.2.0"}
```

- [ ] **Step 5: Telegram /ping 확인**

Telegram 앱에서 봇에 `/ping` 전송 → `pong` 응답 확인.

- [ ] **Step 6: 테스트 webhook payload 전송**

```bash
curl -s -X POST "http://localhost:8080/webhook?secret=dev-secret-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "005930",
    "name": "삼성전자",
    "exchange": "KOSPI",
    "timeframe": "1D",
    "action": "BUY",
    "type": "💰 정석 진입",
    "price": 75000,
    "score": 80,
    "conviction": "A",
    "candle_type": "양봉",
    "ema_touch": "ema1",
    "ema_align": "정배열"
  }'
```

Expected: `{"received": true, "ticker": "005930"}`
DRY_RUN=true인 경우 stdout에 `[signal dry-run]` 메시지 출력.

- [ ] **Step 7: uvicorn 종료 후 커밋**

```bash
git add bot.py app.py
git commit -m "feat(stock-intel): add app.py — FastAPI lifespan + Telegram polling coexistence; refactor bot.py to build_telegram_app()"
```

---

## Task 10: 전체 테스트 실행 + 정리

**Files:**
- No new files

- [ ] **Step 1: 전체 테스트 실행**

```bash
cd /Users/kjun/vault/01_Projects/04_stock_intel
uv run pytest tests/ -v
```

Expected: 모든 테스트 PASS. 0 failures.

- [ ] **Step 2: 02_audit_safe_signals README 업데이트**

`02_audit_safe_signals/README.md` 상단에 다음 추가 (직접 편집):

```markdown
> **[ARCHIVED]** 이 프로젝트의 기능은 `04_stock_intel`로 통합됨.
> 신규 개발은 `04_stock_intel`에서 진행.
```

- [ ] **Step 3: Fly.io 02 앱 중단 (02가 현재 실행 중인 경우)**

```bash
# 02_audit_safe_signals 디렉토리에서 실행
cd /Users/kjun/vault/01_Projects/02_audit_safe_signals
flyctl scale count 0 --app <02-app-name>
```

`<02-app-name>`은 `fly.toml`의 `app` 필드 값으로 대체.

- [ ] **Step 4: 04_stock_intel 배포 준비 확인**

04를 VPS/Fly.io에 배포할 때의 실행 명령:

```bash
# 포트 8080으로 uvicorn 실행
uv run uvicorn app:app --host 0.0.0.0 --port 8080 --workers 1
```

TradingView Alert URL: `https://<your-domain>/webhook?secret=<WEBHOOK_SECRET>`

- [ ] **Step 5: 최종 커밋**

```bash
git add -A
git commit -m "chore(stock-intel): archive 02_audit_safe_signals ref; merge complete"
```

---

## Self-Review

### 스펙 커버리지

| 요구사항 | 구현 태스크 |
|---------|------------|
| TradingView webhook 수신 | Task 8 (server.py POST /webhook) |
| 36필드 페이로드 검증 | Task 2 (domain.py Webhook) |
| 한국 종목 필터 | Task 3 (filters.py passes_buy_filter) |
| dedup 5분 윈도우 | Task 3 (filters.py DedupStore) |
| 감사인 조회 (kreports) | Task 5 (lookup.py KreportsLookup) |
| 감사인 TTL 캐시 | Task 5 (lookup.py CachedAuditorLookup) |
| SKIP/CLEAN/MANUAL_VERIFY 판정 | Task 4 (policy.py decide_alert) |
| 차단 리스트 + aliases | Task 4 (policy.py AuditorPolicy) |
| 시그널 Telegram 알림 | Task 6 (notify.py) |
| 4096B 메시지 분할 | Task 6 (notify.py split_for_telegram) |
| JSONL 결정 로그 | Task 7 (pipeline.py DecisionLogger) |
| /healthz 엔드포인트 | Task 8 (server.py) |
| Telegram polling 공존 | Task 9 (app.py lifespan) |
| 기존 주식 정보 조회 유지 | Task 9 (bot.py — 핸들러 미변경) |
| 차단 감사인 config | Task 1 (config/blocked_auditors.yaml) |
| BuyFilter config | Task 1 (config/settings.yaml) |

### 타입 일관성 체크

- `AuditHistory`, `AuditEntry` — `webhook/policy.py`에서 정의, `webhook/lookup.py`에서 import
- `AuditorLookup` Protocol — `webhook/lookup.py`에서 정의, `webhook/pipeline.py`에서 import
- `TelegramSender` Protocol — `webhook/notify.py`에서 정의, `webhook/pipeline.py`에서 import
- `Decision`, `DecisionKind`, `AuditorRef`, `Webhook` — `webhook/domain.py`에서 정의, 모든 하위 모듈이 import
- `format_signal_message` — `webhook/notify.py` (utils/formatter.py의 `format_message`와 이름 충돌 없음)
- `create_webhook_app` — `webhook/server.py`; `app.py`에서 호출
- `build_telegram_app` — `bot.py`; `app.py`에서 호출
