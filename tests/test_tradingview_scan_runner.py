import json
import subprocess
from pathlib import Path

from signals.tradingview_scan_runner import (
    TradingViewCli,
    build_kr_signal_enrichments,
    format_telegram_exclusion_cards,
    format_scan_report,
    format_telegram_outcome_cards,
    market_for_symbol,
    normalize_scan_symbol,
    priority_sort_key,
    symbol_display_name,
    symbols_from_universe,
)
from signals.tradingview_direct import TradingViewExcludedSignal, TradingViewLabelOutcome, TradingViewTableSnapshot


def test_normalize_scan_symbol_adds_default_exchange_prefixes():
    assert normalize_scan_symbol("005930") == "KRX:005930"
    assert normalize_scan_symbol("AAPL") == "NASDAQ:AAPL"
    assert normalize_scan_symbol("NYSE:PLTR") == "NYSE:PLTR"


def test_symbols_from_universe_prefers_watchlists_and_filters_market(tmp_path: Path):
    path = tmp_path / "universe.json"
    path.write_text(
        json.dumps(
            {
                "symbols": {
                    "NASDAQ:AAPL": {"watchlists": ["관심"]},
                    "NYSE:PLTR": {"watchlists": ["misc"]},
                    "KRX:005930": {"watchlists": ["국장"]},
                    "TSE:7203": {"watchlists": ["일본"]},
                    "BINANCE:BTCUSDT": {"watchlists": ["관심"]},
                }
            }
        ),
        encoding="utf-8",
    )

    assert symbols_from_universe(path, limit=10) == [
        "NASDAQ:AAPL",
        "KRX:005930",
        "TSE:7203",
        "NYSE:PLTR",
    ]
    assert symbols_from_universe(path, limit=10, market="US") == ["NASDAQ:AAPL", "NYSE:PLTR"]


def test_market_for_symbol_includes_japan():
    assert market_for_symbol("KRX:005930") == "KR"
    assert market_for_symbol("NASDAQ:AAPL") == "US"
    assert market_for_symbol("TSE:7203") == "JP"


def test_tradingview_cli_run_uses_timeout(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(command, 0, stdout='{"success": true}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = TradingViewCli(tmp_path, timeout_seconds=7).run(["symbol", "KRX:035420"])

    assert result == {"success": True}
    assert captured["command"][-2:] == ["symbol", "KRX:035420"]
    assert captured["timeout"] == 7


def test_format_scan_report_includes_webhook_distinction_when_empty():
    text = format_scan_report(outcomes=[], errors=[], scanned=["NASDAQ:AAPL"], title="test")

    assert "TradingView 직접 스캔" in text
    assert "웹훅 저장소가 아니라" in text
    assert "NASDAQ:AAPL" in text


def test_format_scan_report_uses_telegram_card_blocks_not_markdown_table():
    outcome = TradingViewLabelOutcome(
        symbol="NASDAQ:AAPL",
        market="US",
        signal_date="2026-04-24",
        first_signal_date="2026-04-24",
        last_signal_date="2026-04-24",
        duplicate_count=1,
        label="💰 진입",
        entry_price=271.12,
        returns={"5d": 3.35, "10d": 8.21, "20d": 13.93},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    text = format_scan_report(outcomes=[outcome], errors=[], scanned=["NASDAQ:AAPL"])

    assert "symbol | date" not in text
    assert "━━━━━━━━" not in text
    assert "1. NASDAQ:AAPL · 기술점수 100점" in text
    assert "시그널: 2026-04-24 · 💰 진입" in text
    assert "신호 기준가: 271" in text
    assert "이후 흐름:" not in text


def test_format_scan_report_includes_lazy_alpha_table_score_when_available():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:321370",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="🔼 피라미딩 추매 1 (50%)",
        entry_price=3975,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    snapshot = TradingViewTableSnapshot(
        signal="🟢 포지션 보유",
        conviction="🟣 S (최고)",
        smart_eval="🍯 꿀통 눌림목 / 21 EMA 지지 (매수 적기)",
        ema_alignment="🟢 정배열 (유지)",
        aux_score=60,
        aux_signal="수급 PB",
        market_sector="📈 강세 정렬",
        trend_energy=None,
        market_control=None,
        rs_score=99,
        volume_strength=2.1,
        high_52w_pct=-23.1,
        stop_loss=3495,
        stop_loss_pct=-12.1,
        target_price=None,
        target_return_pct=None,
        risk_reward=None,
        buy_eligibility="🟢 적합 (조건 충족)",
        fundamental=None,
        eps_growth=[],
        sales_growth=[],
        raw_rows=[],
    )

    text = format_scan_report(
        outcomes=[outcome],
        errors=[],
        scanned=["KRX:321370"],
        table_snapshots={"KRX:321370": snapshot},
    )

    assert "Lazy 원점수: 60점 · 확신 🟣 S (최고)" in text
    assert "Lazy 상태: 🟢 포지션 보유 · 🟢 적합 (조건 충족)" in text
    assert "Lazy 근거: 수급 PB · RS 99점 · 거래량 2.1배 · SL 3,495 (-12.1%)" in text


def test_format_scan_report_includes_exclusion_reason_cards():
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

    text = format_scan_report(
        outcomes=[],
        exclusions=[exclusion],
        errors=[],
        scanned=["KRX:300080"],
    )

    assert "활성 후보: 0건 · 제외: 1건" in text
    assert "제외 후보: 1건" in text
    assert "주요 제외 사유: 📉 모멘텀 SELL / ENTRY: 9000 1건" in text
    assert "1. KRX:300080" in text
    assert "제외: 차트 우측 최신 라벨 · 📉 모멘텀 SELL / ENTRY: 9000" in text
    assert "직전 진입: 2026-05-20 · 💰 진입" in text


def test_format_scan_report_can_hide_exclusions_for_current_entry_view():
    exclusion = TradingViewExcludedSignal(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-20",
        label="💰 진입",
        exit_date=None,
        exit_label="📉 모멘텀 SELL",
        entry_bar_index=297,
        exit_bar_index=409,
        risk_flags=[],
        score_penalty_hint=0,
    )

    text = format_scan_report(
        outcomes=[],
        exclusions=[exclusion],
        errors=[],
        scanned=["KRX:300080"],
        title="📡 현재 진입/매수 후보",
        include_exclusions=False,
    )

    assert "📡 현재 진입/매수 후보" in text
    assert "활성 후보: 0건" in text
    assert "제외 후보" not in text
    assert "모멘텀 SELL" not in text


def test_format_telegram_exclusion_cards_uses_korean_names():
    exclusion = TradingViewExcludedSignal(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-20",
        label="💰 진입",
        exit_date="2026-05-24",
        exit_label="📉 모멘텀 SELL",
        entry_bar_index=297,
        exit_bar_index=309,
        risk_flags=[],
        score_penalty_hint=0,
    )

    text = "\n".join(
        format_telegram_exclusion_cards(
            [exclusion],
            ticker_cache=[{"code": "300080", "name": "플리토", "market": "KOSDAQ"}],
        )
    )

    assert "1. KRX:300080 · 플리토" in text


def test_symbol_display_name_adds_korean_company_name_for_krx_symbol():
    cache = [{"code": "103590", "name": "일진전기", "market": "KOSPI"}]

    assert symbol_display_name("KRX:103590", ticker_cache=cache) == "KRX:103590 · 일진전기"
    assert symbol_display_name("NASDAQ:AAPL", ticker_cache=cache) == "NASDAQ:AAPL"


def test_telegram_cards_include_korean_company_name_for_krx_symbol():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:103590",
        market="KR",
        signal_date="2026-04-22",
        first_signal_date="2026-04-22",
        last_signal_date="2026-04-22",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=87500,
        returns={"5d": 36.69, "10d": 64.69, "20d": 23.77},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    text = "\n".join(
        format_telegram_outcome_cards(
            [outcome],
            ticker_cache=[{"code": "103590", "name": "일진전기", "market": "KOSPI"}],
        )
    )

    assert "1. KRX:103590 · 일진전기 · 기술점수 80점" in text


def test_priority_sort_key_downgrades_large_post_signal_moves():
    fresh = TradingViewLabelOutcome(
        symbol="KRX:012510",
        market="KR",
        signal_date="2026-05-20",
        first_signal_date="2026-05-20",
        last_signal_date="2026-05-20",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=120000,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    reflected = TradingViewLabelOutcome(
        symbol="KRX:103590",
        market="KR",
        signal_date="2026-04-22",
        first_signal_date="2026-04-22",
        last_signal_date="2026-04-22",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=87500,
        returns={"5d": 36.69, "10d": 64.69, "20d": 23.77},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    assert sorted([reflected, fresh], key=priority_sort_key) == [fresh, reflected]


def test_kr_enrichment_adds_supply_fundamental_and_auditor_to_cards():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:103590",
        market="KR",
        signal_date="2026-04-22",
        first_signal_date="2026-04-22",
        last_signal_date="2026-04-22",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=87500,
        returns={"5d": 36.69, "10d": 64.69, "20d": 23.77},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    enrichments = build_kr_signal_enrichments(
        [outcome],
        supply_lookup=lambda ticker: {
            "institution": {"today": 120_000_000, "5d": -340_000_000},
            "foreigner": {"today": -50_000_000, "5d": 880_000_000},
        },
        fundamental_lookup=lambda ticker: {
            "financials": [
                {"year": 2024, "revenue": 1_000_000_000_000, "operating_income": 90_000_000_000},
                {"year": 2025, "revenue": 1_300_000_000_000, "operating_income": 150_000_000_000},
            ],
            "ratios": {"per": 18.2, "pbr": 2.1},
            "comment": "최근 2개년 매출 +30.0% · 영업이익 +66.7%",
        },
        audit_lookup=lambda ticker: {"current_year": 2025, "current_firm": "삼정회계법인"},
    )

    text = "\n".join(
        format_telegram_outcome_cards(
            [outcome],
            ticker_cache=[{"code": "103590", "name": "일진전기", "market": "KOSPI"}],
            enrichments=enrichments,
        )
    )

    assert "감사인: 현재연도 감사인 확인 필요 · 삼정회계법인" in text
    assert "2026 감사인 직접 확인 없음" in text
    assert text.index("감사인:") < text.index("수급:")
    assert "수급: 기관 오늘 +1억 / 5일 -3억 · 외국인 오늘 0억 / 5일 +9억" in text
    assert "실적/밸류: 매출 2025 13,000억 · 영업익 +1,500억 · PER 18.20x · PBR 2.10x" in text
