import json
from pathlib import Path

import pytest

from signals.pipeline import SignalPipeline
from signals.payload import TradingViewSignal
from signals.storage import SignalStore


FIXTURES = Path(__file__).parent / "fixtures"


def load_payload(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_pipeline_sends_blocked_korean_alert(tmp_path):
    sent: list[str] = []

    async def sender(text: str) -> bool:
        sent.append(text)
        return True

    pipeline = SignalPipeline(
        store=SignalStore(tmp_path / "signals.db"),
        audit_lookup=lambda ticker: {"current_year": 2026, "current_firm": "삼정회계법인"},
        send_message=sender,
    )

    result = await pipeline.handle_payload(load_payload("tradingview_v6_2_buy_samsung.json"))

    assert result.independence_status == "BLOCKED_CONFIRMED"
    assert result.telegram_sent is True
    assert sent[0].startswith("🚫 독립성 차단")


@pytest.mark.asyncio
async def test_pipeline_sends_us_manual_verify_alert(tmp_path):
    sent: list[str] = []

    async def sender(text: str) -> bool:
        sent.append(text)
        return True

    pipeline = SignalPipeline(
        store=SignalStore(tmp_path / "signals.db"),
        audit_lookup=lambda ticker: {},
        send_message=sender,
    )

    result = await pipeline.handle_payload(load_payload("tradingview_v6_2_buy_aapl.json"))

    assert result.independence_status == "MANUAL_VERIFY"
    assert result.telegram_sent is True
    assert "EDGAR" in sent[0]


@pytest.mark.asyncio
async def test_pipeline_stores_filtered_sell_without_telegram(tmp_path):
    sent: list[str] = []

    async def sender(text: str) -> bool:
        sent.append(text)
        return True

    store = SignalStore(tmp_path / "signals.db")
    pipeline = SignalPipeline(
        store=store,
        audit_lookup=lambda ticker: {"current_firm": "삼정회계법인"},
        send_message=sender,
    )

    result = await pipeline.handle_payload(load_payload("tradingview_v6_2_sell_samsung.json"))

    assert result.filter_status == "FILTERED"
    assert result.telegram_sent is False
    assert sent == []
    assert store.recent(limit=1)[0].filter_status == "FILTERED"


@pytest.mark.asyncio
async def test_pipeline_allowed_buy_creates_active_signal_state(tmp_path):
    async def sender(text: str) -> bool:
        return True

    store = SignalStore(tmp_path / "signals.db")
    pipeline = SignalPipeline(
        store=store,
        audit_lookup=lambda ticker: {"current_year": 2026, "current_firm": "한영회계법인"},
        send_message=sender,
    )

    await pipeline.handle_payload(load_payload("tradingview_v6_2_buy_samsung.json"))

    active = store.active_signals()
    assert len(active) == 1
    assert active[0].ticker == "005930"
    assert active[0].independence_status == "CLEAR_CONFIRMED"


@pytest.mark.asyncio
async def test_pipeline_sell_closes_active_signal_state(tmp_path):
    async def sender(text: str) -> bool:
        return True

    store = SignalStore(tmp_path / "signals.db")
    store.upsert_active_signal(
        signal=TradingViewSignal.model_validate(load_payload("tradingview_v6_2_buy_samsung.json")),
        market="KR",
        independence_status="CLEAR",
        activated_at=100,
        ttl_seconds=8 * 3600,
    )
    pipeline = SignalPipeline(
        store=store,
        audit_lookup=lambda ticker: {"current_firm": "한영회계법인"},
        send_message=sender,
    )

    await pipeline.handle_payload(load_payload("tradingview_v6_2_sell_samsung.json"))

    assert store.active_signals() == []
