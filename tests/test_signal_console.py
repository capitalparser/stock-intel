import json
from pathlib import Path

from telegram import InlineKeyboardMarkup

from signals.console import (
    ConsoleState,
    build_console_keyboard,
    format_console,
    format_signal_detail,
    parse_console_args,
)
from signals.payload import TradingViewSignal
from signals.storage import SignalStore


FIXTURES = Path(__file__).parent / "fixtures"


def load_signal(fixture_name: str, **overrides) -> TradingViewSignal:
    payload = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
    payload.update(overrides)
    return TradingViewSignal.model_validate(payload)


def test_store_recent_since_filters_by_received_at(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_samsung.json"),
        market="KR",
        independence_status="CLEAR",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=100,
    )
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_aapl.json"),
        market="US",
        independence_status="MANUAL_VERIFY",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=200,
    )

    rows = store.recent_since(150)

    assert [row.ticker for row in rows] == ["AAPL"]


def test_store_latest_for_ticker_matches_prefixed_and_plain_kr_tickers(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_samsung.json", ticker="KRX:005930"),
        market="KR",
        independence_status="BLOCKED",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=100,
    )
    store.put_event(
        signal=load_signal("tradingview_v6_2_sell_samsung.json", ticker="KRX:005930"),
        market="KR",
        independence_status="BLOCKED",
        filter_status="FILTERED",
        telegram_sent=False,
        received_at=300,
    )

    row = store.latest_for_ticker("005930")

    assert row is not None
    assert row.ticker == "KRX:005930"
    assert row.action == "SELL"


def test_store_active_signal_roundtrip_and_close(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    signal = load_signal("tradingview_v6_2_buy_samsung.json", ticker="KRX:005930")
    store.upsert_active_signal(
        signal=signal,
        market="KR",
        independence_status="CLEAR",
        activated_at=100,
        ttl_seconds=8 * 3600,
    )

    active = store.active_signals(now=200)

    assert len(active) == 1
    assert active[0].ticker == "KRX:005930"
    assert active[0].base_type == "💰 정석 진입"
    assert active[0].expires_at == 100 + 8 * 3600

    store.close_active_signal("005930", closed_at=300)

    assert store.active_signals(now=400) == []


def test_parse_console_args_defaults_to_buy_all_8h():
    state = parse_console_args([])

    assert state.tab == "BUY"
    assert state.market == "ALL"
    assert state.hours == 8
    assert state.view == "ACTIVE"


def test_parse_console_args_keeps_buy_kr_8h_state():
    state = parse_console_args(["buy", "kr", "8h"])

    assert state.tab == "BUY"
    assert state.market == "KR"
    assert state.hours == 8
    assert state.view == "ACTIVE"


def test_parse_console_args_supports_recent_event_view():
    state = parse_console_args(["recent", "sell", "jp", "24h"])

    assert state.view == "RECENT"
    assert state.tab == "SELL"
    assert state.market == "JP"
    assert state.hours == 24


def test_parse_console_args_supports_score_sort():
    state = parse_console_args(["kr", "점수"])

    assert state.market == "KR"
    assert state.sort == "SCORE"


def test_format_console_filters_recent_buy_kr_rows(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_samsung.json", name="삼성전자"),
        market="KR",
        independence_status="CLEAR",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=1000,
    )
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_aapl.json", name="Apple"),
        market="US",
        independence_status="MANUAL_VERIFY",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=1000,
    )

    text = format_console(
        rows=store.recent_since(0),
        state=ConsoleState(view="RECENT", tab="BUY", market="KR", hours=8),
        now=1000,
    )

    assert "Lazy Alpha Signal Console" in text
    assert "매수" in text
    assert "삼성전자" in text
    assert "Apple" not in text


def test_format_console_shows_active_signal_state(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.upsert_active_signal(
        signal=load_signal("tradingview_v6_2_buy_samsung.json", name="삼성전자"),
        market="KR",
        independence_status="CLEAR",
        activated_at=1000,
        ttl_seconds=8 * 3600,
    )

    text = format_console(
        rows=store.active_signals(now=1200),
        state=ConsoleState(view="ACTIVE", tab="BUY", market="KR", hours=8),
        now=1200,
    )

    assert "보기: 현재 활성" in text
    assert "active 3m" in text
    assert "삼성전자" in text


def test_format_console_can_sort_by_master_score(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.upsert_active_signal(
        signal=load_signal(
            "tradingview_v6_2_buy_samsung.json",
            name="낮은점수",
            score=50,
            conviction="C",
            daily_rs=70,
            daily_dist_from_high=-20.0,
            sl=69000,
        ),
        market="KR",
        independence_status="CLEAR",
        activated_at=1000,
        ttl_seconds=8 * 3600,
    )
    store.upsert_active_signal(
        signal=load_signal(
            "tradingview_v6_2_buy_aapl.json",
            name="높은점수",
            score=90,
            conviction="S",
            daily_rs=91,
            daily_dist_from_high=-2.0,
            sl=188.0,
        ),
        market="US",
        independence_status="CLEAR",
        activated_at=900,
        ttl_seconds=8 * 3600,
    )

    text = format_console(
        rows=store.active_signals(now=1200),
        state=ConsoleState(view="ACTIVE", tab="BUY", market="ALL", hours=8, sort="SCORE"),
        now=1200,
    )

    assert "정렬: 점수순" in text
    assert text.index("높은점수") < text.index("낮은점수")


def test_format_signal_detail_shows_latest_indicator_judgment(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_samsung.json", name="삼성전자"),
        market="KR",
        independence_status="BLOCKED",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=1000,
    )

    row = store.latest_for_ticker("005930")
    text = format_signal_detail(row, now=1000)

    assert "삼성전자" in text
    assert "정석 진입" in text
    assert "Score 75" in text
    assert "독립성: BLOCKED" in text


def test_build_console_keyboard_uses_tab_like_callback_payloads():
    keyboard = build_console_keyboard(ConsoleState(tab="BUY", market="ALL", hours=8))

    assert isinstance(keyboard, InlineKeyboardMarkup)
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert "sig:view=ACTIVE;tab=SELL;market=ALL;hours=8;sort=TIME" in callbacks
    assert "sig:view=ACTIVE;tab=BUY;market=KR;hours=8;sort=TIME" in callbacks
    assert "sig:view=ACTIVE;tab=BUY;market=ALL;hours=24;sort=TIME" in callbacks
    assert "sig:view=RECENT;tab=BUY;market=ALL;hours=8;sort=TIME" in callbacks
    assert "sig:view=ACTIVE;tab=BUY;market=ALL;hours=8;sort=SCORE" in callbacks
