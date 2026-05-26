import json
import socket
from types import SimpleNamespace
from pathlib import Path

import bot
from signals.tradingview_direct import TradingViewExcludedSignal, TradingViewLabelOutcome
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


def test_render_lazy_alpha_status_reports_active_single_symbol(monkeypatch):
    outcome = TradingViewLabelOutcome(
        symbol="KRX:103590",
        market="KR",
        signal_date="2026-05-20",
        first_signal_date="2026-05-20",
        last_signal_date="2026-05-20",
        duplicate_count=1,
        label="💰 진입",
        entry_price=87500,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    monkeypatch.setattr(
        bot,
        "scan_tradingview_symbols",
        lambda symbols, **kwargs: SimpleNamespace(outcomes=[outcome], exclusions=[], errors=[], scanned=symbols),
    )

    text = bot.render_lazy_alpha_status_for_symbol("KRX:103590")

    assert "판정: 매수 후보 유지" in text
    assert "기술점수: 100점" in text
    assert "확인: 이후 청산/SELL 라벨 없음" in text


def test_render_lazy_alpha_status_reports_excluded_single_symbol(monkeypatch):
    exclusion = TradingViewExcludedSignal(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-20",
        label="💰 진입",
        exit_date=None,
        exit_label="📉 모멘텀 SELL\nENTRY: 9000",
        entry_bar_index=297,
        exit_bar_index=409,
        risk_flags=[],
        score_penalty_hint=0,
    )

    monkeypatch.setattr(
        bot,
        "scan_tradingview_symbols",
        lambda symbols, **kwargs: SimpleNamespace(outcomes=[], exclusions=[exclusion], errors=[], scanned=symbols),
    )

    text = bot.render_lazy_alpha_status_for_symbol("KRX:300080")

    assert "판정: 매수 후보 아님" in text
    assert "기술점수: 100점" in text
    assert "차트 우측 최신 라벨 · 📉 모멘텀 SELL / ENTRY: 9000" in text
    assert "직전 진입: 2026-05-20 · 💰 진입" in text


def test_render_stock_lookup_report_appends_lazy_alpha_section(monkeypatch):
    monkeypatch.setattr(
        bot,
        "fetch_all",
        lambda ticker: (
            {"error": "skip"},
            {"error": "skip"},
            {"error": "skip"},
            {"error": "skip"},
            {"error": "skip"},
        ),
    )
    monkeypatch.setattr(
        bot,
        "render_lazy_alpha_status_for_symbol",
        lambda symbol: f"📡 Lazy Alpha 현재 상태\n대상: {symbol}",
    )

    text = bot.render_stock_lookup_report("300080", "플리토")

    assert "📊 플리토 (300080)" in text
    assert "📡 Lazy Alpha 현재 상태" in text
    assert "대상: KRX:300080" in text


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
    assert bot.parse_tradingview_scan_text("/진입 kr") == ["활성만", "점수", "50", "동기화", "kr"]
    assert bot.parse_tradingview_scan_text("매수 us 20") == ["활성만", "점수", "50", "동기화", "us", "20"]
    assert bot.parse_tradingview_scan_text("krscan 20") == ["국장", "점수", "50", "동기화", "20"]
    assert bot.parse_tradingview_scan_text("/tvscan KRX:005930") == ["KRX:005930"]
    assert bot.parse_tradingview_scan_text("삼성전자") is None


def test_parse_leading_discovery_text_supports_korean_command():
    assert bot.parse_leading_discovery_text("/선행 kr 20") == ["kr", "20"]
    assert bot.parse_leading_discovery_text("발굴 국장") == ["국장"]
    assert bot.parse_leading_discovery_text("삼성전자") is None


def test_render_leading_discovery_combines_supply_and_technical_scores(monkeypatch):
    monkeypatch.setattr(bot, "_leading_kr_symbol_pool", lambda limit, use_universe: ["KRX:103590"])
    monkeypatch.setattr(bot, "_ticker_name_map", lambda: {"103590": "일진전기"})
    monkeypatch.setattr(
        bot,
        "fetch_supply",
        lambda ticker: {
            "institution": {"today": 200_000_000, "5d": 1_200_000_000, "20d": 4_800_000_000},
            "foreigner": {"today": 100_000_000, "5d": 800_000_000, "20d": 2_200_000_000},
            "daily": [{"institution": 1, "foreigner": 1}] * 5,
        },
    )
    monkeypatch.setattr(
        bot,
        "fetch_technical",
        lambda ticker: {
            "price": 84_000,
            "ma20": 82_000,
            "ma50": 79_000,
            "ma150": 70_000,
            "ma200": 66_000,
            "ma_trend": "정배열",
            "trend_template": "통과",
            "volume_ratio": 1.25,
            "rsi14": 58,
            "bb_pct": 66,
            "from_52w_high_pct": -12,
            "from_52w_low_pct": 42,
            "signal": "중립",
        },
    )
    monkeypatch.setattr(
        bot,
        "fetch_fundamental",
        lambda ticker: {
            "financials": [
                {"year": 2024, "revenue": 100, "operating_income": 8, "operating_cash_flow": 4},
                {"year": 2025, "revenue": 125, "operating_income": 14, "operating_cash_flow": 7},
            ]
        },
    )
    monkeypatch.setattr(bot, "fetch_audit_firm", lambda ticker: {})
    monkeypatch.setattr(bot, "_leading_auditor_summary", lambda audit: "차단 없음")

    text = bot.render_leading_discovery(["kr", "10"])

    assert "🔎 국장 선행 후보" in text
    assert "KRX:103590 · 일진전기" in text
    assert "기관 20일 순매수" in text
    assert "수급" in text


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
