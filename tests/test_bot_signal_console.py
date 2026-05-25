import json
import socket
from pathlib import Path

import bot
from signals.payload import TradingViewSignal
from signals.storage import SignalStore
from signals.universe import build_universe_snapshot, save_universe_snapshot


FIXTURES = Path(__file__).parent / "fixtures"


def load_signal(name: str) -> TradingViewSignal:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return TradingViewSignal.model_validate(payload)


def test_render_signal_console_uses_state_db_path_and_args(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.db"
    store = SignalStore(db_path)
    store.upsert_active_signal(
        signal=load_signal("tradingview_v6_2_buy_samsung.json"),
        market="KR",
        independence_status="CLEAR",
        activated_at=1000,
        ttl_seconds=8 * 3600,
    )
    monkeypatch.setenv("STATE_DB_PATH", str(db_path))
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "missing_universe.json"))

    text, keyboard = bot.render_signal_console(["kr", "8h"], now=1000)

    assert "Lazy Alpha Signal Console" in text
    assert "삼성전자" in text
    assert keyboard.inline_keyboard[1][1].callback_data == "sig:view=ACTIVE;tab=SELL;market=KR;hours=8;sort=TIME"


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


def test_signal_text_shortcuts_open_signal_console():
    assert bot.is_signal_console_text("시그널") is True
    assert bot.is_signal_console_text("신호") is True
    assert bot.is_signal_console_text("signals") is True
    assert bot.is_signal_console_text("삼성전자") is False


def test_parse_signal_console_text_supports_args_and_slash():
    assert bot.parse_signal_console_text("/신호 점수") == ["점수"]
    assert bot.parse_signal_console_text("신호 kr 점수") == ["kr", "점수"]
    assert bot.parse_signal_console_text("/signals us score") == ["us", "score"]
    assert bot.parse_signal_console_text("삼성전자") is None


def test_parse_tradingview_scan_text_supports_korean_scan_command():
    assert bot.parse_tradingview_scan_text("/스캔 NASDAQ:AAPL 3") == ["NASDAQ:AAPL", "3"]
    assert bot.parse_tradingview_scan_text("현재신호 us 5 점수") == ["us", "5", "점수"]
    assert bot.parse_tradingview_scan_text("/국장스캔") == ["국장", "점수", "50", "동기화"]
    assert bot.parse_tradingview_scan_text("krscan 20") == ["국장", "점수", "50", "동기화", "20"]
    assert bot.parse_tradingview_scan_text("/tvscan KRX:005930") == ["KRX:005930"]
    assert bot.parse_tradingview_scan_text("삼성전자") is None


def test_strip_korean_slash_command_handles_args_and_bot_suffix():
    command, args = bot._strip_korean_slash_command("/신호@stock_intel_bot kr 8h")

    assert command == "신호"
    assert args == ["kr", "8h"]


def test_render_korean_signal_command_defaults_to_buy_console(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.db"
    store = SignalStore(db_path)
    store.upsert_active_signal(
        signal=load_signal("tradingview_v6_2_buy_samsung.json"),
        market="KR",
        independence_status="CLEAR",
        activated_at=1000,
        ttl_seconds=8 * 3600,
    )
    monkeypatch.setenv("STATE_DB_PATH", str(db_path))
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "missing_universe.json"))

    text, _keyboard = bot.render_signal_console(["buy"], now=1000)

    assert "탭: 매수" in text
    assert "삼성전자" in text


def test_render_universe_summary_uses_snapshot_path(tmp_path, monkeypatch):
    path = tmp_path / "universe.json"
    snapshot = build_universe_snapshot(
        [
            {"type": "custom", "id": "1", "name": "국장", "symbols": ["KRX:005930"]},
            {"type": "custom", "id": "2", "name": "관심", "symbols": ["NASDAQ:AAPL"]},
        ],
        fetched_at="2026-05-25T00:00:00Z",
    )
    save_universe_snapshot(snapshot, path)
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(path))

    text = bot.render_universe_summary()

    assert "TradingView Universe" in text
    assert "전체 심볼: 2" in text
    assert "국장: 1" in text


def test_render_signal_console_filters_to_universe_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.db"
    universe_path = tmp_path / "universe.json"
    store = SignalStore(db_path)
    store.upsert_active_signal(
        signal=load_signal("tradingview_v6_2_buy_samsung.json").model_copy(
            update={"ticker": "KRX:005930"}
        ),
        market="KR",
        independence_status="CLEAR",
        activated_at=1000,
        ttl_seconds=8 * 3600,
    )
    store.upsert_active_signal(
        signal=load_signal("tradingview_v6_2_buy_aapl.json"),
        market="US",
        independence_status="MANUAL_VERIFY",
        activated_at=1000,
        ttl_seconds=8 * 3600,
    )
    snapshot = build_universe_snapshot(
        [{"type": "custom", "id": "1", "name": "국장", "symbols": ["KRX:005930"]}],
        fetched_at="2026-05-25T00:00:00Z",
    )
    save_universe_snapshot(snapshot, universe_path)
    monkeypatch.setenv("STATE_DB_PATH", str(db_path))
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(universe_path))

    text, _keyboard = bot.render_signal_console([], now=1200)

    assert "삼성전자" in text
    assert "Apple" not in text


def test_render_sync_universe_uses_env_paths(tmp_path, monkeypatch):
    universe_path = tmp_path / "universe.json"

    def fake_sync(*, mcp_dir, output_path):
        assert mcp_dir == "/tmp/tradingview-mcp"
        assert output_path == str(universe_path)
        return build_universe_snapshot(
            [{"type": "custom", "id": "1", "name": "관심", "symbols": ["NASDAQ:AAPL"]}],
            fetched_at="2026-05-25T00:00:00Z",
        )

    monkeypatch.setenv("TRADINGVIEW_MCP_DIR", "/tmp/tradingview-mcp")
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(universe_path))
    monkeypatch.setattr(bot, "sync_universe_from_tradingview", fake_sync)

    text = bot.render_sync_universe()

    assert "동기화 완료" in text
    assert "전체 심볼: 1" in text


def test_assert_port_available_raises_for_bound_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        try:
            bot.assert_port_available("127.0.0.1", port)
        except RuntimeError as exc:
            assert "already in use" in str(exc)
        else:
            raise AssertionError("expected RuntimeError for occupied port")
    finally:
        sock.close()
