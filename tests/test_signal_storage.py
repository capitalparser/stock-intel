import json
from pathlib import Path

from signals.payload import TradingViewSignal
from signals.storage import SignalStore


FIXTURES = Path(__file__).parent / "fixtures"


def test_store_put_and_recent_roundtrip(tmp_path):
    payload = json.loads((FIXTURES / "tradingview_v6_2_buy_aapl.json").read_text())
    signal = TradingViewSignal.model_validate(payload)
    store = SignalStore(tmp_path / "signals.db")

    store.put_event(
        signal=signal,
        market="US",
        independence_status="MANUAL_VERIFY",
        filter_status="ALLOWED",
        telegram_sent=True,
    )

    rows = store.recent(limit=10)
    assert len(rows) == 1
    assert rows[0].ticker == "AAPL"
    assert rows[0].market == "US"
    assert rows[0].independence_status == "MANUAL_VERIFY"
    assert rows[0].filter_status == "ALLOWED"
    assert rows[0].telegram_sent is True
    assert json.loads(rows[0].payload_json)["sb_z_score"] == 1.42


def test_events_for_audit_returns_buy_events_only(tmp_path):
    buy_payload = json.loads((FIXTURES / "tradingview_v6_2_buy_aapl.json").read_text())
    sell_payload = json.loads((FIXTURES / "tradingview_v6_2_sell_samsung.json").read_text())
    store = SignalStore(tmp_path / "signals.db")

    store.put_event(
        signal=TradingViewSignal.model_validate(buy_payload),
        market="US",
        independence_status="CLEAR",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=100,
    )
    store.put_event(
        signal=TradingViewSignal.model_validate(sell_payload),
        market="KR",
        independence_status="CLEAR",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=200,
    )

    rows = store.events_for_audit(limit=10)

    assert [row.action for row in rows] == ["BUY"]
    assert rows[0].ticker == "AAPL"
