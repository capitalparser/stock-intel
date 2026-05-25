import json
from pathlib import Path

import bot
from signals.payload import TradingViewSignal
from signals.storage import SignalStore


FIXTURES = Path(__file__).parent / "fixtures"


def load_signal(name: str) -> TradingViewSignal:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return TradingViewSignal.model_validate(payload)


def test_render_signal_console_uses_state_db_path_and_args(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.db"
    store = SignalStore(db_path)
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_samsung.json"),
        market="KR",
        independence_status="CLEAR",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=1000,
    )
    monkeypatch.setenv("STATE_DB_PATH", str(db_path))

    text, keyboard = bot.render_signal_console(["kr", "8h"], now=1000)

    assert "Lazy Alpha Signal Console" in text
    assert "삼성전자" in text
    assert keyboard.inline_keyboard[0][1].callback_data == "sig:tab=SELL;market=KR;hours=8"


def test_render_signal_detail_uses_latest_matching_ticker(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.db"
    store = SignalStore(db_path)
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_samsung.json").model_copy(
            update={"ticker": "KRX:005930"}
        ),
        market="KR",
        independence_status="BLOCKED",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=1000,
    )
    monkeypatch.setenv("STATE_DB_PATH", str(db_path))

    text = bot.render_signal_detail("005930", now=1000)

    assert "삼성전자" in text
    assert "독립성: BLOCKED" in text


def test_help_text_shortcuts_do_not_fall_through_to_stock_lookup():
    assert bot.is_help_text("기능") is True
    assert bot.is_help_text("도움말") is True
    assert bot.is_help_text("메뉴") is True
    assert bot.is_help_text("삼성전자") is False
