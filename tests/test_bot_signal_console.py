import json
import socket
import sqlite3
from types import SimpleNamespace
from pathlib import Path

import bot
from signals.tradingview_direct import (
    TradingViewExcludedSignal,
    TradingViewLabelFlowItem,
    TradingViewLabelOutcome,
    TradingViewTableSnapshot,
)
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
        lambda symbols, **kwargs: SimpleNamespace(
            outcomes=[outcome],
            exclusions=[],
            errors=[],
            scanned=symbols,
            label_flows={
                "KRX:103590": [
                    TradingViewLabelFlowItem("2026-05-13", "🛠️ 셋업 형성 중", 90),
                    TradingViewLabelFlowItem("2026-05-20", "💰 진입", 95),
                ]
            },
            table_snapshots={
                "KRX:103590": TradingViewTableSnapshot(
                    signal="🟢 포지션 보유",
                    conviction="🟢 A (강한)",
                    smart_eval="📈 안정적 우상향 / 편안한 추세 (홀딩)",
                    ema_alignment="🟢 정배열 (유지)",
                    aux_score=70,
                    aux_signal="돌파 W패턴 BO",
                    market_sector="📈 강세 정렬",
                    trend_energy="🔥 상승 가속 (23.4)",
                    market_control="🐂 매수세 (🔥강력)",
                    rs_score=99,
                    volume_strength=2.1,
                    high_52w_pct=-9.1,
                    stop_loss=59300,
                    stop_loss_pct=-10.1,
                    target_price=85900,
                    target_return_pct=30.1,
                    risk_reward="1 : 3.1 (👍 좋음)",
                    buy_eligibility="🟢 적합 (조건 충족)",
                    fundamental="🌤️ 펀더멘털: 우수 (Good)",
                    eps_growth=["82.5%", "-18.1%", "-31.0%"],
                    sales_growth=["13.2%", "6.9%", "5.3%"],
                    raw_rows=[],
                )
            },
        ),
    )

    text = bot.render_lazy_alpha_status_for_symbol("KRX:103590")

    assert "핵심 요약" in text
    assert "다음 행동: 분할 진입과 무효화 라벨 확인" in text
    assert "상세 근거" in text
    assert text.index("핵심 요약") < text.index("상세 근거")
    assert text.index("상세 근거") < text.index("Lazy 테이블")
    assert text.index("Lazy 테이블") < text.index("최근 1개월 라벨 흐름")
    assert "판정: 매수 후보 유지" in text
    assert "최종판정: 진입 가능 · 활성 매수 라벨" in text
    assert "기술점수: 100점" in text
    assert "확인: 이후 청산/SELL 라벨 없음" in text
    assert "최근 1개월 라벨 흐름" in text
    assert "2026-05-13  🛠️ 셋업 형성 중" in text
    assert "2026-05-20  💰 진입" in text
    assert "라벨 해석" in text
    assert "단계: 초기 진입" in text
    assert "행동: 초기 진입 후보" in text
    assert "Lazy 테이블" in text
    assert "Lazy 점수: 70점 · 확신 🟢 A (강한)" in text
    assert "리스크/보상: SL 59,300 (-10.1%) · TP1 85,900 (+30.1%) · R/R 1 : 3.1 (👍 좋음)" in text


def test_render_lazy_alpha_status_prefers_latest_active_label_for_single_symbol(monkeypatch):
    old = TradingViewLabelOutcome(
        symbol="KRX:437730",
        market="KR",
        signal_date="2025-12-15",
        first_signal_date="2025-12-15",
        last_signal_date="2025-12-15",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=52000,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    latest = TradingViewLabelOutcome(
        symbol="KRX:437730",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="🚀 돌파 진입 @SR↩",
        entry_price=60000,
        returns={"5d": None, "10d": None, "20d": None},
        context={"dist_sma20_pct": 21, "dist_sma50_pct": 15.2},
        risk_flags=[],
        score_penalty_hint=0,
    )
    monkeypatch.setattr(
        bot,
        "scan_tradingview_symbols",
        lambda symbols, **kwargs: SimpleNamespace(outcomes=[old, latest], exclusions=[], errors=[], scanned=symbols, label_flows={}),
    )

    text = bot.render_lazy_alpha_status_for_symbol("KRX:437730")

    assert "시그널: 2026-05-26 · 🚀 돌파 진입 @SR↩" in text
    assert "신호 기준가: 60,000원" in text


def test_render_lazy_alpha_status_warns_when_table_conflicts_with_active_label(monkeypatch):
    outcome = TradingViewLabelOutcome(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-21",
        first_signal_date="2026-05-21",
        last_signal_date="2026-05-21",
        duplicate_count=1,
        label="💰 진입",
        entry_price=10860,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    monkeypatch.setattr(
        bot,
        "scan_tradingview_symbols",
        lambda symbols, **kwargs: SimpleNamespace(
            outcomes=[outcome],
            exclusions=[],
            errors=[],
            scanned=symbols,
            label_flows={},
            table_snapshots={
                "KRX:300080": TradingViewTableSnapshot(
                    signal="⚪️ 관망",
                    conviction="🔴 D (역배열/꼬임)",
                    smart_eval="떨어지는 칼날 (접근 금지)",
                    ema_alignment="🔴 약배열 (유지)",
                    aux_score=1,
                    aux_signal="대기",
                    market_sector=None,
                    trend_energy=None,
                    market_control="🐻 매도세 (우위)",
                    rs_score=17,
                    volume_strength=1.33,
                    high_52w_pct=-55.1,
                    stop_loss=None,
                    stop_loss_pct=None,
                    target_price=None,
                    target_return_pct=None,
                    risk_reward=None,
                    buy_eligibility="⚠️ 미충족  진입",
                    fundamental=None,
                    eps_growth=[],
                    sales_growth=[],
                    raw_rows=[],
                )
            },
        ),
    )

    text = bot.render_lazy_alpha_status_for_symbol("KRX:300080")

    assert "최종판정: 매수 금지 · Lazy 테이블 관망/역배열" in text
    assert "상태 경고: Lazy 테이블 관망/역배열/매도세" in text
    assert "기술점수: 65점" in text
    assert "2025-12-15" not in text


def test_render_lazy_alpha_status_scans_single_symbol_with_latest_cluster_policy(monkeypatch):
    captured = {}

    def fake_scan(symbols, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(outcomes=[], exclusions=[], errors=[], scanned=symbols, label_flows={})

    monkeypatch.setattr(bot, "scan_tradingview_symbols", fake_scan)

    bot.render_lazy_alpha_status_for_symbol("KRX:321370")

    assert captured["entry_policy"] == "last"
    assert captured["duplicate_window_bars"] == 5


def test_render_tradingview_scan_uses_latest_cluster_policy(monkeypatch):
    captured = {}

    def fake_scan(symbols, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            outcomes=[],
            exclusions=[],
            errors=[],
            scanned=symbols,
            label_flows={},
            table_snapshots={},
        )

    monkeypatch.setattr(bot, "scan_tradingview_symbols", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    bot.render_tradingview_scan(["KRX:437730"])

    assert captured["entry_policy"] == "last"


def test_render_tradingview_scan_batches_full_universe(monkeypatch, tmp_path):
    universe_path = tmp_path / "universe.json"
    universe_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(universe_path))
    monkeypatch.setenv("TRADINGVIEW_SCAN_BATCH_SIZE", "2")
    monkeypatch.setattr(
        bot,
        "symbols_from_universe",
        lambda path, limit, market=None: [
            "KRX:000001",
            "KRX:000002",
            "KRX:000003",
            "KRX:000004",
            "KRX:000005",
        ][:limit],
    )
    calls = []

    def fake_scan(symbols, **kwargs):
        calls.append(list(symbols))
        return SimpleNamespace(
            outcomes=[],
            exclusions=[],
            errors=[],
            scanned=list(symbols),
            label_flows={},
            table_snapshots={},
        )

    monkeypatch.setattr(bot, "scan_tradingview_symbols", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    text = bot.render_tradingview_scan(["전체", "kr", "5"])

    assert calls == [
        ["KRX:000001", "KRX:000002"],
        ["KRX:000003", "KRX:000004"],
        ["KRX:000005"],
    ]
    assert "TradingView 전체 Watchlist 스캔" in text
    assert "요청: 5종목 · 배치: 3회" in text


def test_render_lazy_alpha_transitions_records_and_reports_changes(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("STATE_DB_PATH", str(db_path))
    monkeypatch.setattr(bot, "parse_tradingview_scan_args", lambda args: {"symbols": ["KRX:437730"]})
    scans = [
        SimpleNamespace(
            outcomes=[],
            exclusions=[],
            errors=[],
            scanned=["KRX:437730"],
            label_flows={"KRX:437730": [TradingViewLabelFlowItem("2026-05-25", "🛠️ 셋업 형성 중", 10)]},
            table_snapshots={},
        ),
        SimpleNamespace(
            outcomes=[
                TradingViewLabelOutcome(
                    symbol="KRX:437730",
                    market="KR",
                    signal_date="2026-05-26",
                    first_signal_date="2026-05-26",
                    last_signal_date="2026-05-26",
                    duplicate_count=1,
                    label="🚀 돌파 진입",
                    entry_price=60000,
                    returns={},
                    context={},
                    risk_flags=[],
                    score_penalty_hint=0,
                )
            ],
            exclusions=[],
            errors=[],
            scanned=["KRX:437730"],
            label_flows={},
            table_snapshots={},
        ),
    ]

    monkeypatch.setattr(bot, "_scan_tradingview_symbols_batched", lambda symbols, batch_size: (scans.pop(0), 1))

    first = bot.render_lazy_alpha_transition_report(["kr"])
    second = bot.render_lazy_alpha_transition_report(["kr"])

    assert "새로 알릴 상태 전환이 없습니다." in first
    assert "전환: 셋업 관찰 → 활성 매수" in second
    assert "현재: 2026-05-26 · 🚀 돌파 진입" in second


def test_render_lazy_alpha_transitions_reports_blocked_buy_when_table_conflicts(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("STATE_DB_PATH", str(db_path))
    monkeypatch.setattr(bot, "parse_tradingview_scan_args", lambda args: {"symbols": ["KRX:300080"]})
    scans = [
        SimpleNamespace(
            outcomes=[],
            exclusions=[],
            errors=[],
            scanned=["KRX:300080"],
            label_flows={"KRX:300080": [TradingViewLabelFlowItem("2026-05-25", "🛠️ 셋업 형성 중", 10)]},
            table_snapshots={},
        ),
        SimpleNamespace(
            outcomes=[
                TradingViewLabelOutcome(
                    symbol="KRX:300080",
                    market="KR",
                    signal_date="2026-05-26",
                    first_signal_date="2026-05-26",
                    last_signal_date="2026-05-26",
                    duplicate_count=1,
                    label="💰 진입",
                    entry_price=10860,
                    returns={},
                    context={},
                    risk_flags=[],
                    score_penalty_hint=0,
                )
            ],
            exclusions=[],
            errors=[],
            scanned=["KRX:300080"],
            label_flows={},
            table_snapshots={
                "KRX:300080": TradingViewTableSnapshot(
                    signal="⚪️ 관망",
                    conviction="🔴 D (역배열/꼬임)",
                    smart_eval="떨어지는 칼날 (접근 금지)",
                    ema_alignment="🔴 약배열 (유지)",
                    aux_score=1,
                    aux_signal="대기",
                    market_sector=None,
                    trend_energy=None,
                    market_control="🐻 매도세 (우위)",
                    rs_score=17,
                    volume_strength=1.33,
                    high_52w_pct=-55.1,
                    stop_loss=None,
                    stop_loss_pct=None,
                    target_price=None,
                    target_return_pct=None,
                    risk_reward=None,
                    buy_eligibility="⚠️ 미충족  진입",
                    fundamental=None,
                    eps_growth=[],
                    sales_growth=[],
                    raw_rows=[],
                )
            },
        ),
    ]

    monkeypatch.setattr(bot, "_scan_tradingview_symbols_batched", lambda symbols, batch_size: (scans.pop(0), 1))

    first = bot.render_lazy_alpha_transition_report(["kr"])
    second = bot.render_lazy_alpha_transition_report(["kr"])

    assert "새로 알릴 상태 전환이 없습니다." in first
    assert "전환: 셋업 관찰 → 매수 차단" in second
    assert "판정: 매수 금지" in second
    assert "행동: 추세 회복 전까지 제외" in second


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
        lambda symbols, **kwargs: SimpleNamespace(outcomes=[], exclusions=[exclusion], errors=[], scanned=symbols, label_flows={}),
    )

    text = bot.render_lazy_alpha_status_for_symbol("KRX:300080")

    assert "핵심 요약" in text
    assert "다음 행동: 재셋업 전까지 관망" in text
    assert "최근 신호: 차트 우측 최신 라벨 · 📉 모멘텀 SELL / ENTRY: 9000" in text
    assert "상세 근거" in text
    assert text.index("핵심 요약") < text.index("상세 근거")
    assert "판정: 매수 후보 아님" in text
    assert "최종판정: 매수 금지 · 강한 매도/손절 라벨: 📉 모멘텀 SELL / ENTRY: 9000" in text
    assert "기술점수: 100점" not in text
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


def test_render_stock_lookup_report_escalates_auditor_independence_alert(monkeypatch):
    monkeypatch.setattr(
        bot,
        "fetch_all",
        lambda ticker: (
            {"error": "skip"},
            {"error": "skip"},
            {"error": "skip"},
            {"error": "skip"},
            {"current_year": 2026, "current_firm": "삼정회계법인", "recent": [{"year": 2026, "firm": "삼정회계법인"}]},
        ),
    )

    text = bot.render_stock_lookup_report("083650", "비에이치아이", include_lazy_alpha=False)

    assert "🚫 독립성 차단 — 매입 검토 금지" in text
    assert text.index("🚫 독립성 차단") < text.index("📊 비에이치아이")


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
    assert bot.parse_tradingview_scan_text("/스캔 전체 kr 80") == ["전체", "kr", "80"]
    assert bot.parse_tradingview_scan_text("krscan 20") == ["국장", "점수", "50", "동기화", "20"]
    assert bot.parse_tradingview_scan_text("/tvscan KRX:005930") == ["KRX:005930"]
    assert bot.parse_tradingview_scan_text("삼성전자") is None


def test_parse_tradingview_scan_args_marks_only_user_symbols_as_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "universe.json"))
    monkeypatch.setattr(bot, "sync_universe_from_tradingview", lambda **kwargs: None)
    monkeypatch.setattr(bot, "symbols_from_universe", lambda path, limit, market=None: ["NASDAQ:MSFT"][:limit])

    universe_options = bot.parse_tradingview_scan_args(["활성만", "점수", "50", "동기화", "us", "1"])
    explicit_options = bot.parse_tradingview_scan_args(["us", "NASDAQ:AAPL"])
    korean_market_options = bot.parse_tradingview_scan_args(["미국장", "1"])
    jp_market_options = bot.parse_tradingview_scan_args(["일장", "1"])

    assert universe_options["symbols"] == ["NASDAQ:MSFT"]
    assert universe_options["explicit_symbols"] is False
    assert explicit_options["explicit_symbols"] is True
    assert korean_market_options["market"] == "US"
    assert korean_market_options["symbols"] == ["NASDAQ:MSFT"]
    assert jp_market_options["market"] == "JP"


def test_parse_lazy_alpha_transition_text_supports_korean_command():
    assert bot.parse_lazy_alpha_transition_text("/변화 kr 50") == ["kr", "50"]
    assert bot.parse_lazy_alpha_transition_text("상태변화 전체 us 80") == ["전체", "us", "80"]
    assert bot.parse_lazy_alpha_transition_text("삼성전자") is None


def test_parse_leading_discovery_text_supports_korean_command():
    assert bot.parse_leading_discovery_text("/선행 kr 20") == ["kr", "20"]
    assert bot.parse_leading_discovery_text("발굴 국장") == ["국장"]
    assert bot.parse_leading_discovery_text("삼성전자") is None


def test_parse_backtest_text_supports_korean_command():
    assert bot.parse_backtest_text("/검증 kr 20") == ["kr", "20"]
    assert bot.parse_backtest_text("백테스트 국장 50") == ["국장", "50"]
    assert bot.parse_backtest_args(["일본장", "10"]) == {"market": "JP", "limit": 10}
    assert bot.parse_backtest_text("삼성전자") is None


def test_parse_recommendation_text_supports_korean_command():
    assert bot.parse_recommendation_text("/추천 kr 20") == ["kr", "20"]
    assert bot.parse_recommendation_text("후보 us 30") == ["us", "30"]
    assert bot.parse_recommendation_text("추천 미국 10") == ["미국", "10"]
    assert bot.parse_recommendation_text("추천 일장 10") == ["일장", "10"]
    assert bot.parse_recommendation_text("삼성전자") is None


def test_parse_recommendation_cooldown_text_supports_korean_command():
    assert bot.parse_recommendation_cooldown_text("/추천쿨다운") == []
    assert bot.parse_recommendation_cooldown_text("추천쿨다운 초기화") == ["초기화"]
    assert bot.parse_recommendation_cooldown_text("추천 us") is None


def test_parse_recommendation_cache_text_supports_korean_command():
    assert bot.parse_recommendation_cache_text("/추천캐시") == []
    assert bot.parse_recommendation_cache_text("추천캐시 초기화") == ["초기화"]
    assert bot.parse_recommendation_cache_text("추천 us") is None


def test_render_recommendation_cache_reports_stats_and_clear(monkeypatch, tmp_path):
    db_path = tmp_path / "scan_cache.sqlite3"
    monkeypatch.setenv("TRADINGVIEW_SCAN_CACHE_PATH", str(db_path))
    monkeypatch.setenv("TRADINGVIEW_SCAN_CACHE_TTL_SECONDS", "600")
    cache = bot._tradingview_scan_cache()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO tradingview_scan_cache(cache_key, fetched_at, payload_json) VALUES (?, ?, ?)",
            ("fresh", 1_000, "{}"),
        )
        conn.execute(
            "INSERT INTO tradingview_scan_cache(cache_key, fetched_at, payload_json) VALUES (?, ?, ?)",
            ("old", 1, "{}"),
        )
        conn.commit()
    monkeypatch.setattr("signals.tradingview_scan_cache.time.time", lambda: 1_100)

    text = bot.render_recommendation_cache([])

    assert "🧰 추천 스캔 캐시" in text
    assert "전체: 2건" in text
    assert "유효: 1건" in text
    assert "만료: 1건" in text

    pruned = bot.render_recommendation_cache(["정리"])

    assert "만료 정리 완료" in pruned
    assert "삭제 1건" in pruned
    assert cache.stats()["total"] == 1
    assert cache.stats()["active"] == 1

    cleared = bot.render_recommendation_cache(["초기화"])

    assert "초기화 완료" in cleared
    assert cache.stats()["total"] == 0


def test_render_recommendation_cooldown_report_lists_active_symbols(monkeypatch, tmp_path):
    path = tmp_path / "cooldown.json"
    path.write_text(
        json.dumps(
            {
                "AMEX:BMNR": {"last_failed_at": 1_000, "error": "symbol not found"},
                "NASDAQ:OLD": {"last_failed_at": -3_000, "error": "old"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RECOMMENDATION_ERROR_COOLDOWN_PATH", str(path))
    monkeypatch.setenv("RECOMMENDATION_ERROR_COOLDOWN_SECONDS", "3600")
    monkeypatch.setattr(bot.time, "time", lambda: 1_600)

    text = bot.render_recommendation_cooldown([])

    assert "🧊 추천 오류 심볼 쿨다운" in text
    assert "활성: 1건" in text
    assert "AMEX:BMNR" in text
    assert "남은 50분" in text
    assert "symbol not found" in text
    assert "NASDAQ:OLD" not in text
    state = json.loads(path.read_text(encoding="utf-8"))
    assert "AMEX:BMNR" in state
    assert "NASDAQ:OLD" not in state


def test_render_recommendation_cooldown_clear_resets_state(monkeypatch, tmp_path):
    path = tmp_path / "cooldown.json"
    path.write_text(json.dumps({"AMEX:BMNR": {"last_failed_at": 1_000, "error": "bad"}}), encoding="utf-8")
    monkeypatch.setenv("RECOMMENDATION_ERROR_COOLDOWN_PATH", str(path))

    text = bot.render_recommendation_cooldown(["초기화"])

    assert "초기화 완료" in text
    assert json.loads(path.read_text(encoding="utf-8")) == {}


def test_render_recommendation_cooldown_clears_single_symbol(monkeypatch, tmp_path):
    path = tmp_path / "cooldown.json"
    path.write_text(
        json.dumps(
            {
                "AMEX:BMNR": {"last_failed_at": 1_000, "error": "bad"},
                "NASDAQ:MSFT": {"last_failed_at": 1_000, "error": "temporary"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RECOMMENDATION_ERROR_COOLDOWN_PATH", str(path))

    text = bot.render_recommendation_cooldown(["해제", "AMEX:BMNR"])

    state = json.loads(path.read_text(encoding="utf-8"))
    assert "AMEX:BMNR 해제 완료" in text
    assert "AMEX:BMNR" not in state
    assert "NASDAQ:MSFT" in state


def test_render_backtest_report_uses_saved_buy_events(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.db"
    store = SignalStore(db_path)
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_samsung.json"),
        market="KR",
        independence_status="CLEAR",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=1_767_288_600,
    )
    monkeypatch.setenv("STATE_DB_PATH", str(db_path))
    provider = bot.PriceHistoryProvider()
    provider.closes = lambda **kwargs: [
        bot.PricePoint(date=f"2026-01-{day:02d}", close=100 + day)
        for day in range(2, 24)
    ]

    text = bot.render_backtest_report(["kr", "20"], price_provider=provider)

    assert "🧪 Master Score 사후검증" in text
    assert "샘플: 1건 · 유효: 1건" in text
    assert "점수대별 20거래일 성과" in text
    assert "ticker |" not in text


def test_render_backtest_report_supports_us_events_with_injected_provider(tmp_path, monkeypatch):
    db_path = tmp_path / "signals.db"
    store = SignalStore(db_path)
    store.put_event(
        signal=load_signal("tradingview_v6_2_buy_aapl.json"),
        market="US",
        independence_status="MANUAL_VERIFY",
        filter_status="ALLOWED",
        telegram_sent=True,
        received_at=1_767_288_600,
    )
    monkeypatch.setenv("STATE_DB_PATH", str(db_path))
    provider = bot.PriceHistoryProvider()
    provider.closes = lambda **kwargs: [
        bot.PricePoint(date=f"2026-01-{day:02d}", close=190 + day)
        for day in range(2, 24)
    ]

    text = bot.render_backtest_report(["us", "20"], price_provider=provider)

    assert "현재 가격 히스토리 provider는 국장" not in text
    assert "샘플: 1건 · 유효: 1건" in text
    assert "독립성표본: 원천 확인 필요 1건" in text


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


def test_render_signal_recommendations_uses_scan_results(monkeypatch):
    outcome = TradingViewLabelOutcome(
        symbol="KRX:103590",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=87500,
        returns={"5d": None, "10d": None, "20d": None},
        context={"dist_sma20_pct": 4.2, "dist_sma50_pct": 8.5, "stop_distance_pct": 8.0},
        risk_flags=[],
        score_penalty_hint=0,
    )
    monkeypatch.setattr(
        bot,
        "parse_tradingview_scan_args",
        lambda args: {"symbols": ["KRX:103590"], "market": "KR"},
    )
    monkeypatch.setattr(
        bot,
        "_scan_tradingview_symbols_batched",
        lambda symbols, batch_size, **kwargs: (
            SimpleNamespace(
                outcomes=[outcome],
                exclusions=[],
                errors=[],
                scanned=["KRX:103590"],
                label_flows={},
                table_snapshots={},
            ),
            1,
        ),
    )
    monkeypatch.setattr(
        bot,
        "build_signal_enrichments",
        lambda outcomes, **kwargs: {},
    )

    text = bot.render_signal_recommendations(["kr", "20"])

    assert "🎯 시세 반영 전 추천 후보" in text
    assert "KRX:103590" in text


def test_render_signal_recommendations_supplements_universe_after_initial_errors(monkeypatch, tmp_path):
    outcome = TradingViewLabelOutcome(
        symbol="NASDAQ:AAPL",
        market="US",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=190,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "universe.json"))
    monkeypatch.setenv("RECOMMENDATION_ERROR_COOLDOWN_PATH", str(tmp_path / "cooldown.json"))
    monkeypatch.setattr(
        bot,
        "parse_tradingview_scan_args",
        lambda args: {"symbols": ["AMEX:BMNR"], "market": "US", "limit": 1},
    )
    monkeypatch.setattr(
        bot,
        "symbols_from_universe",
        lambda path, limit, market=None: ["AMEX:BMNR", "NASDAQ:AAPL", "NYSE:PLTR"][:limit],
    )
    calls = []

    def fake_scan(symbols, batch_size, **kwargs):
        calls.append(list(symbols))
        if symbols == ["AMEX:BMNR"]:
            return (
                SimpleNamespace(outcomes=[], exclusions=[], errors=[("AMEX:BMNR", "bad symbol")], scanned=[], label_flows={}, table_snapshots={}),
                1,
            )
        return (
            SimpleNamespace(outcomes=[outcome], exclusions=[], errors=[], scanned=["NASDAQ:AAPL"], label_flows={}, table_snapshots={}),
            1,
        )

    monkeypatch.setattr(bot, "_scan_tradingview_symbols_batched", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    text = bot.render_signal_recommendations(["us", "1"])

    assert calls == [["AMEX:BMNR"], ["NASDAQ:AAPL", "NYSE:PLTR"]]
    assert "NASDAQ:AAPL" in text
    assert "오류: AMEX:BMNR" in text


def test_render_signal_recommendations_cools_down_repeated_error_symbols(monkeypatch, tmp_path):
    outcome = TradingViewLabelOutcome(
        symbol="NASDAQ:AAPL",
        market="US",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=190,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "universe.json"))
    monkeypatch.setenv("RECOMMENDATION_ERROR_COOLDOWN_PATH", str(tmp_path / "cooldown.json"))
    monkeypatch.setenv("RECOMMENDATION_ERROR_COOLDOWN_SECONDS", "3600")
    monkeypatch.setattr(
        bot,
        "parse_tradingview_scan_args",
        lambda args: {"symbols": ["AMEX:BMNR"], "market": "US", "limit": 1, "explicit_symbols": False},
    )
    monkeypatch.setattr(
        bot,
        "symbols_from_universe",
        lambda path, limit, market=None: ["AMEX:BMNR", "NASDAQ:AAPL"][:limit],
    )
    calls = []

    def fake_scan(symbols, batch_size, **kwargs):
        calls.append(list(symbols))
        if symbols == ["AMEX:BMNR"]:
            return (
                SimpleNamespace(outcomes=[], exclusions=[], errors=[("AMEX:BMNR", "bad symbol")], scanned=[], label_flows={}, table_snapshots={}),
                1,
            )
        return (
            SimpleNamespace(outcomes=[outcome], exclusions=[], errors=[], scanned=["NASDAQ:AAPL"], label_flows={}, table_snapshots={}),
            1,
        )

    monkeypatch.setattr(bot, "_scan_tradingview_symbols_batched", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    first = bot.render_signal_recommendations(["us", "1"])
    second = bot.render_signal_recommendations(["us", "1"])

    assert calls == [["AMEX:BMNR"], ["NASDAQ:AAPL"], ["NASDAQ:AAPL"]]
    assert "오류: AMEX:BMNR" in first
    assert "쿨다운 제외: AMEX:BMNR" in second
    assert "NASDAQ:AAPL" in second


def test_render_signal_recommendations_sync_bypasses_error_cooldown(monkeypatch, tmp_path):
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "universe.json"))
    monkeypatch.setenv("RECOMMENDATION_ERROR_COOLDOWN_PATH", str(tmp_path / "cooldown.json"))
    monkeypatch.setenv("RECOMMENDATION_ERROR_COOLDOWN_SECONDS", "3600")
    monkeypatch.setattr(
        bot,
        "parse_tradingview_scan_args",
        lambda args: {
            "symbols": ["AMEX:BMNR"],
            "market": "US",
            "limit": 1,
            "explicit_symbols": False,
            "sync": "동기화" in args,
        },
    )
    monkeypatch.setattr(
        bot,
        "symbols_from_universe",
        lambda path, limit, market=None: ["AMEX:BMNR", "NASDAQ:AAPL"][:limit],
    )
    calls = []

    def fake_scan(symbols, batch_size, **kwargs):
        calls.append(list(symbols))
        if symbols == ["AMEX:BMNR"]:
            return (
                SimpleNamespace(outcomes=[], exclusions=[], errors=[("AMEX:BMNR", "bad symbol")], scanned=[], label_flows={}, table_snapshots={}),
                1,
            )
        return (
            SimpleNamespace(outcomes=[], exclusions=[], errors=[], scanned=list(symbols), label_flows={}, table_snapshots={}),
            1,
        )

    monkeypatch.setattr(bot, "_scan_tradingview_symbols_batched", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    bot.render_signal_recommendations(["us", "1"])
    bot.render_signal_recommendations(["us", "1"])
    bot.render_signal_recommendations(["us", "1", "동기화"])

    assert calls == [["AMEX:BMNR"], ["NASDAQ:AAPL"], ["NASDAQ:AAPL"], ["AMEX:BMNR"], ["NASDAQ:AAPL"]]


def test_render_signal_recommendations_supplements_when_initial_scan_has_no_candidate(monkeypatch, tmp_path):
    outcome = TradingViewLabelOutcome(
        symbol="NASDAQ:AAPL",
        market="US",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=190,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "universe.json"))
    monkeypatch.setattr(
        bot,
        "parse_tradingview_scan_args",
        lambda args: {"symbols": ["NASDAQ:MSFT"], "market": "US", "limit": 1, "explicit_symbols": False},
    )
    monkeypatch.setattr(
        bot,
        "symbols_from_universe",
        lambda path, limit, market=None: ["NASDAQ:MSFT", "NASDAQ:AAPL", "NYSE:PLTR"][:limit],
    )
    calls = []

    def fake_scan(symbols, batch_size, **kwargs):
        calls.append(list(symbols))
        if symbols == ["NASDAQ:MSFT"]:
            return (
                SimpleNamespace(outcomes=[], exclusions=[], errors=[], scanned=["NASDAQ:MSFT"], label_flows={}, table_snapshots={}),
                1,
            )
        return (
            SimpleNamespace(outcomes=[outcome], exclusions=[], errors=[], scanned=["NASDAQ:AAPL"], label_flows={}, table_snapshots={}),
            1,
        )

    monkeypatch.setattr(bot, "_scan_tradingview_symbols_batched", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    text = bot.render_signal_recommendations(["us", "1"])

    assert calls == [["NASDAQ:MSFT"], ["NASDAQ:AAPL", "NYSE:PLTR"]]
    assert "NASDAQ:AAPL" in text


def test_render_signal_recommendations_keeps_supplementing_until_target_candidates(monkeypatch, tmp_path):
    pltr = TradingViewLabelOutcome(
        symbol="NYSE:PLTR",
        market="US",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=125,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    nvda = TradingViewLabelOutcome(
        symbol="NASDAQ:NVDA",
        market="US",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=180,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "universe.json"))
    monkeypatch.setenv("TRADINGVIEW_SCAN_BATCH_SIZE", "1")
    monkeypatch.setenv("RECOMMENDATION_SCAN_FALLBACK_MULTIPLIER", "4")
    monkeypatch.setattr(
        bot,
        "parse_tradingview_scan_args",
        lambda args: {"symbols": ["NASDAQ:MSFT"], "market": "US", "limit": 2, "explicit_symbols": False},
    )
    monkeypatch.setattr(
        bot,
        "symbols_from_universe",
        lambda path, limit, market=None: [
            "NASDAQ:MSFT",
            "NASDAQ:AAPL",
            "NYSE:PLTR",
            "NASDAQ:NVDA",
            "NYSE:SNOW",
        ][:limit],
    )
    calls = []

    def fake_scan(symbols, batch_size, **kwargs):
        calls.append(list(symbols))
        outcomes = []
        if symbols == ["NYSE:PLTR"]:
            outcomes = [pltr]
        elif symbols == ["NASDAQ:NVDA"]:
            outcomes = [nvda]
        return (
            SimpleNamespace(
                outcomes=outcomes,
                exclusions=[],
                errors=[],
                scanned=list(symbols),
                label_flows={},
                table_snapshots={},
            ),
            1,
        )

    monkeypatch.setattr(bot, "_scan_tradingview_symbols_batched", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    text = bot.render_signal_recommendations(["us", "2"])

    assert calls == [["NASDAQ:MSFT", "NASDAQ:AAPL"], ["NYSE:PLTR"], ["NASDAQ:NVDA"]]
    assert "NYSE:PLTR" in text
    assert "NASDAQ:NVDA" in text


def test_render_signal_recommendations_uses_cached_scan_without_forcing_universe_sync(monkeypatch, tmp_path):
    outcome = TradingViewLabelOutcome(
        symbol="NASDAQ:AAPL",
        market="US",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=190,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "universe.json"))
    monkeypatch.setenv("TRADINGVIEW_SCAN_CACHE_PATH", str(tmp_path / "scan_cache.sqlite3"))
    monkeypatch.setenv("TRADINGVIEW_SCAN_CACHE_TTL_SECONDS", "600")
    monkeypatch.setattr(
        bot,
        "sync_universe_from_tradingview",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("recommendation should not force universe sync")),
    )
    monkeypatch.setattr(
        bot,
        "symbols_from_universe",
        lambda path, limit, market=None: ["NASDAQ:AAPL"],
    )
    calls = []

    def fake_scan(symbols, **kwargs):
        calls.append(list(symbols))
        return SimpleNamespace(
            outcomes=[outcome],
            exclusions=[],
            errors=[],
            scanned=["NASDAQ:AAPL"],
            label_flows={},
            table_snapshots={},
        )

    monkeypatch.setattr(bot, "scan_tradingview_symbols", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    first = bot.render_signal_recommendations(["us", "1"])
    second = bot.render_signal_recommendations(["us", "1"])

    assert calls == [["NASDAQ:AAPL"]]
    assert "NASDAQ:AAPL" in first
    assert "NASDAQ:AAPL" in second


def test_render_signal_recommendations_sync_arg_bypasses_scan_cache(monkeypatch, tmp_path):
    outcome = TradingViewLabelOutcome(
        symbol="NASDAQ:AAPL",
        market="US",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=190,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "universe.json"))
    monkeypatch.setenv("TRADINGVIEW_SCAN_CACHE_PATH", str(tmp_path / "scan_cache.sqlite3"))
    monkeypatch.setenv("TRADINGVIEW_SCAN_CACHE_TTL_SECONDS", "600")
    monkeypatch.setattr(bot, "sync_universe_from_tradingview", lambda **kwargs: None)
    monkeypatch.setattr(bot, "symbols_from_universe", lambda path, limit, market=None: ["NASDAQ:AAPL"])
    calls = []

    def fake_scan(symbols, **kwargs):
        calls.append(list(symbols))
        return SimpleNamespace(
            outcomes=[outcome],
            exclusions=[],
            errors=[],
            scanned=["NASDAQ:AAPL"],
            label_flows={},
            table_snapshots={},
        )

    monkeypatch.setattr(bot, "scan_tradingview_symbols", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    bot.render_signal_recommendations(["us", "1"])
    bot.render_signal_recommendations(["us", "1", "동기화"])

    assert calls == [["NASDAQ:AAPL"], ["NASDAQ:AAPL"]]


def test_render_signal_recommendations_does_not_supplement_explicit_symbol(monkeypatch, tmp_path):
    monkeypatch.setenv("UNIVERSE_SNAPSHOT_PATH", str(tmp_path / "universe.json"))
    monkeypatch.setattr(
        bot,
        "parse_tradingview_scan_args",
        lambda args: {"symbols": ["NASDAQ:MSFT"], "market": "US", "limit": 1, "explicit_symbols": True},
    )
    monkeypatch.setattr(
        bot,
        "symbols_from_universe",
        lambda path, limit, market=None: ["NASDAQ:MSFT", "NASDAQ:AAPL", "NYSE:PLTR"][:limit],
    )
    calls = []

    def fake_scan(symbols, batch_size, **kwargs):
        calls.append(list(symbols))
        return (
            SimpleNamespace(outcomes=[], exclusions=[], errors=[], scanned=["NASDAQ:MSFT"], label_flows={}, table_snapshots={}),
            1,
        )

    monkeypatch.setattr(bot, "_scan_tradingview_symbols_batched", fake_scan)
    monkeypatch.setattr(bot, "build_signal_enrichments", lambda outcomes, **kwargs: {})

    text = bot.render_signal_recommendations(["NASDAQ:MSFT"])

    assert calls == [["NASDAQ:MSFT"]]
    assert "표시할 추천 후보가 없습니다." in text


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
