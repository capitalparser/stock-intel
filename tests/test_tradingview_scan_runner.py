import json
import subprocess
from pathlib import Path

from signals.tradingview_scan_runner import (
    TradingViewCli,
    build_kr_signal_enrichments,
    build_signal_enrichments,
    format_recommendation_report,
    format_telegram_exclusion_cards,
    format_scan_report,
    format_telegram_outcome_cards,
    market_for_symbol,
    normalize_scan_symbol,
    priority_sort_key,
    recommend_signal_candidates,
    symbol_display_name,
    symbols_from_universe,
)
from signals.tradingview_direct import TradingViewExcludedSignal, TradingViewLabelFlowItem, TradingViewLabelOutcome, TradingViewTableSnapshot


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
    assert "최종판정: 진입 가능 · 활성 매수 라벨" in text
    assert "시그널: 2026-04-24 · 💰 진입" in text
    assert "신호 기준가: 271" in text
    assert "이후 흐름:" not in text


def test_format_scan_report_includes_label_flow_interpretation():
    outcome = TradingViewLabelOutcome(
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

    text = format_scan_report(
        outcomes=[outcome],
        errors=[],
        scanned=["KRX:437730"],
        label_flows={
            "KRX:437730": [
                TradingViewLabelFlowItem("2026-05-22", "🛠️ 셋업 형성 중", 1),
                TradingViewLabelFlowItem("2026-05-26", "🚀 돌파 진입", 2),
            ]
        },
    )

    assert "흐름평가: 셋업 후 돌파 · 양호 · 점수영향 +5" in text
    assert "흐름행동: 돌파 유지와 거래량 지속 확인" in text


def test_format_scan_report_applies_negative_label_flow_adjustment_to_score():
    outcome = TradingViewLabelOutcome(
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

    text = format_scan_report(
        outcomes=[outcome],
        errors=[],
        scanned=["KRX:437730"],
        label_flows={
            "KRX:437730": [
                TradingViewLabelFlowItem("2026-05-20", "💰 진입", 1),
                TradingViewLabelFlowItem("2026-05-21", "⚠️ 8선 이탈", 2),
                TradingViewLabelFlowItem("2026-05-22", "💰 진입", 3),
                TradingViewLabelFlowItem("2026-05-23", "💣 돌파 청산", 4),
                TradingViewLabelFlowItem("2026-05-24", "🛠️ 셋업 형성 중", 5),
                TradingViewLabelFlowItem("2026-05-25", "🚀 돌파 진입", 6),
            ]
        },
    )

    assert "1. KRX:437730 · 삼현 · 기술점수 92점" in text
    assert "흐름평가: 휩쏘 후 재돌파 · 위험 · 점수영향 -8" in text


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
    assert "Lazy 추세: 🟢 정배열 (유지) · RS 99점 · 거래량 2.1배 · 52주고점 -23.1%" in text
    assert "Lazy 근거: 수급 PB · 🍯 꿀통 눌림목 / 21 EMA 지지 (매수 적기)" in text
    assert "Lazy 시장: 📈 강세 정렬" in text
    assert "Lazy 리스크: SL 3,495 (-12.1%)" in text


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
    assert "분류: 매수 금지 · 강한 매도/손절 라벨" in text
    assert "행동: 재셋업 전까지 관망" in text
    assert "직전 진입: 2026-05-20 · 💰 진입" in text


def test_format_scan_report_includes_auditor_alert_for_kr_exclusions():
    exclusion = TradingViewExcludedSignal(
        symbol="KRX:083650",
        market="KR",
        signal_date="2026-05-20",
        label="💰 진입",
        exit_date="2026-05-26",
        exit_label="💸 최종 청산",
        entry_bar_index=297,
        exit_bar_index=409,
        risk_flags=[],
        score_penalty_hint=0,
    )
    enrichments = build_kr_signal_enrichments(
        [exclusion],
        supply_lookup=lambda ticker: {},
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {"current_year": 2026, "current_firm": "삼정회계법인"},
    )

    text = format_scan_report(
        outcomes=[],
        exclusions=[exclusion],
        errors=[],
        scanned=["KRX:083650"],
        enrichments=enrichments,
    )

    assert "독립성알림: 🚫 독립성 차단 — 매입 검토 금지" in text
    assert "감사인: 독립성 차단 · 삼정회계법인" in text


def test_format_scan_report_shows_only_current_exclusion_per_inactive_symbol():
    active = TradingViewLabelOutcome(
        symbol="KRX:321370",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="🔼 피라미딩 추매 1 (50%)",
        entry_price=3975,
        returns={},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    active_old_exit = TradingViewExcludedSignal(
        symbol="KRX:321370",
        market="KR",
        signal_date="2026-03-26",
        label="🚀 돌파 진입",
        exit_date="2026-03-30",
        exit_label="✂️ 부분 익절고려",
        entry_bar_index=100,
        exit_bar_index=104,
        risk_flags=[],
        score_penalty_hint=0,
    )
    inactive_old_exit = TradingViewExcludedSignal(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-04-20",
        label="🚀 돌파 진입 @SR↩",
        exit_date="2026-04-23",
        exit_label="💣 돌파 청산",
        entry_bar_index=200,
        exit_bar_index=203,
        risk_flags=[],
        score_penalty_hint=0,
    )
    inactive_latest_exit = TradingViewExcludedSignal(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-21",
        label="💰 진입",
        exit_date=None,
        exit_label="⚠️ 8선 이탈",
        entry_bar_index=240,
        exit_bar_index=260,
        risk_flags=[],
        score_penalty_hint=0,
    )

    text = format_scan_report(
        outcomes=[active],
        exclusions=[active_old_exit, inactive_old_exit, inactive_latest_exit],
        errors=[],
        scanned=["KRX:321370", "KRX:300080"],
    )

    assert "활성 후보: 1건 · 제외: 1건" in text
    assert "제외 후보: 1건" in text
    assert "KRX:321370" in text
    assert "2026-03-30" not in text
    assert "2026-04-23" not in text
    assert "차트 우측 최신 라벨 · ⚠️ 8선 이탈" in text
    assert "분류: 추세 훼손 · 지지선 이탈" in text
    assert "행동: 8선/21EMA 회복과 재진입 라벨 대기" in text
    assert "직전 진입: 2026-05-21 · 💰 진입" in text


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


def test_telegram_cards_rank_kr_candidates_by_composite_supply_score():
    strong_supply = TradingViewLabelOutcome(
        symbol="KRX:103590",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=87500,
        returns={},
        context={},
        risk_flags=[],
        score_penalty_hint=10,
    )
    weak_supply = TradingViewLabelOutcome(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=9050,
        returns={},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    enrichments = build_kr_signal_enrichments(
        [strong_supply, weak_supply],
        supply_lookup=lambda ticker: {
            "103590": {
                "institution": {"today": 200_000_000, "5d": 1_200_000_000, "20d": 4_800_000_000},
                "foreigner": {"today": 100_000_000, "5d": 800_000_000, "20d": 2_200_000_000},
                "daily": [{"institution": 1, "foreigner": 1}] * 5,
            },
            "300080": {
                "institution": {"today": -100_000_000, "5d": -800_000_000, "20d": -2_400_000_000},
                "foreigner": {"today": -200_000_000, "5d": -700_000_000, "20d": -1_900_000_000},
                "daily": [],
            },
        }[ticker],
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {"current_year": 2026, "current_firm": "한영회계법인"},
    )

    text = "\n".join(
        format_telegram_outcome_cards(
            [weak_supply, strong_supply],
            enrichments=enrichments,
            ticker_cache=[
                {"code": "103590", "name": "일진전기", "market": "KOSPI"},
                {"code": "300080", "name": "플리토", "market": "KOSDAQ"},
            ],
        )
    )

    assert text.index("1. KRX:103590 · 일진전기 · 종합점수 92점 · 기술점수 90점") < text.index(
        "2. KRX:300080 · 플리토 · 종합점수 75점 · 기술점수 100점"
    )


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
    assert "독립성알림: 🟡 독립성 확인 필요 — 원천 확인 전 매입 보류" in text
    assert "2026 감사인 직접 확인 없음" in text
    assert text.index("독립성알림:") < text.index("감사인:")
    assert text.index("감사인:") < text.index("수급:")
    assert "수급: 기관 오늘 +1억 / 5일 -3억 · 외국인 오늘 0억 / 5일 +9억" in text
    assert "실적/밸류: 매출 2025 13,000억 · 영업익 +1,500억 · PER 18.20x · PBR 2.10x" in text


def test_kr_enrichment_escalates_blocked_auditor_before_scores():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:083650",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=98300,
        returns={},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    enrichments = build_kr_signal_enrichments(
        [outcome],
        supply_lookup=lambda ticker: {},
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {"current_year": 2026, "current_firm": "삼정KPMG"},
    )

    text = "\n".join(format_telegram_outcome_cards([outcome], enrichments=enrichments))

    assert "독립성알림: 🚫 독립성 차단 — 매입 검토 금지" in text
    assert "감사인: 독립성 차단 · 삼정회계법인" in text


def test_recommend_signal_candidates_blocks_kpmg_independence_risk():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:083650",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=98300,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    enrichments = build_signal_enrichments(
        [outcome],
        supply_lookup=lambda ticker: {
            "institution": {"today": 500_000_000, "5d": 2_000_000_000, "20d": 8_000_000_000},
            "foreigner": {"today": 300_000_000, "5d": 1_500_000_000, "20d": 5_000_000_000},
            "daily": [{"institution": 1, "foreigner": 1}] * 5,
        },
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {"current_year": 2026, "current_firm": "삼정KPMG"},
    )

    recommendations = recommend_signal_candidates([outcome], enrichments=enrichments)

    assert recommendations[0].state == "독립성 차단"
    assert recommendations[0].recommendation_score <= 40
    assert "독립성 차단" in recommendations[0].risks
    assert "매입 검토 금지" in recommendations[0].next_action

    text = format_recommendation_report(
        recommendations,
        scanned=1,
        errors=[],
        ticker_cache=[{"code": "083650", "name": "비에이치아이", "market": "KOSDAQ"}],
    )

    assert "상태: 독립성 차단" in text
    assert "리스크: 독립성 차단" in text
    assert "다음 행동: 매입 검토 금지, 독립성 원천 확인 전 후보 제외" in text


def test_recommend_signal_candidates_holds_when_auditor_rollover_is_unverified():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:095340",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=197300,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    enrichments = build_signal_enrichments(
        [outcome],
        supply_lookup=lambda ticker: {
            "institution": {"today": 100_000_000, "5d": 900_000_000, "20d": 2_500_000_000},
            "foreigner": {"today": 50_000_000, "5d": 700_000_000, "20d": 1_500_000_000},
            "daily": [{"institution": 1, "foreigner": 1}] * 5,
        },
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {
            "recent": [
                {"year": 2025, "firm": "안진회계법인"},
                {"year": 2024, "firm": "안진회계법인"},
            ],
            "current_firm": "안진회계법인",
        },
    )

    recommendations = recommend_signal_candidates([outcome], enrichments=enrichments)

    assert recommendations[0].state == "원천확인 대기"
    assert "감사인 원천 확인 필요" in recommendations[0].risks
    assert recommendations[0].next_action == "독립성 원천 확인 전 매입 보류"


def test_kr_enrichment_scores_supply_accumulation_for_scan_cards():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:103590",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=87500,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    enrichments = build_kr_signal_enrichments(
        [outcome],
        supply_lookup=lambda ticker: {
            "institution": {"today": 200_000_000, "5d": 1_200_000_000, "20d": 4_800_000_000},
            "foreigner": {"today": 100_000_000, "5d": 800_000_000, "20d": 2_200_000_000},
            "daily": [
                {"institution": 200_000_000, "foreigner": 100_000_000},
                {"institution": 150_000_000, "foreigner": 50_000_000},
                {"institution": 120_000_000, "foreigner": 80_000_000},
                {"institution": 90_000_000, "foreigner": 20_000_000},
                {"institution": -10_000_000, "foreigner": 30_000_000},
            ],
        },
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {"current_year": 2026, "current_firm": "한영회계법인"},
    )

    text = "\n".join(format_telegram_outcome_cards([outcome], enrichments=enrichments))

    assert "수급점수: 35/35 · 동반 매집" in text
    assert "수급근거: 기관 20일 순매수 +48억 · 기관 5일 순매수 +12억 · 외국인 20일 순매수 +22억" in text


def test_kr_enrichment_marks_distribution_supply_risk_for_scan_cards():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=9050,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    enrichments = build_kr_signal_enrichments(
        [outcome],
        supply_lookup=lambda ticker: {
            "institution": {"today": -100_000_000, "5d": -800_000_000, "20d": -2_400_000_000},
            "foreigner": {"today": -200_000_000, "5d": -700_000_000, "20d": -1_900_000_000},
            "daily": [],
        },
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {},
    )

    text = "\n".join(format_telegram_outcome_cards([outcome], enrichments=enrichments))

    assert "수급점수: 0/35 · 수급 약함" in text
    assert "수급리스크: 기관+외국인 20일 동반 순매도" in text


def test_recommend_signal_candidates_prioritizes_fresh_unreflected_entries():
    fresh = TradingViewLabelOutcome(
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
    reflected = TradingViewLabelOutcome(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=9050,
        returns={"5d": 18.5, "10d": 31.2, "20d": 55.0},
        context={"dist_sma20_pct": 22.0, "dist_sma50_pct": 38.0, "stop_distance_pct": 18.0},
        risk_flags=[],
        score_penalty_hint=0,
    )
    enrichments = build_kr_signal_enrichments(
        [fresh, reflected],
        supply_lookup=lambda ticker: {
            "103590": {
                "institution": {"today": 200_000_000, "5d": 1_200_000_000, "20d": 4_800_000_000},
                "foreigner": {"today": 100_000_000, "5d": 800_000_000, "20d": 2_200_000_000},
                "daily": [{"institution": 1, "foreigner": 1}] * 5,
            },
            "300080": {
                "institution": {"today": -100_000_000, "5d": -800_000_000, "20d": -2_400_000_000},
                "foreigner": {"today": -200_000_000, "5d": -700_000_000, "20d": -1_900_000_000},
                "daily": [],
            },
        }[ticker],
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {"current_year": 2026, "current_firm": "한영회계법인"},
    )

    recommendations = recommend_signal_candidates(
        [reflected, fresh],
        enrichments=enrichments,
        label_flows={
            "KRX:103590": [
                TradingViewLabelFlowItem("2026-05-25", "🛠️ 셋업 형성 중", 1),
                TradingViewLabelFlowItem("2026-05-26", "🚀 돌파 진입", 2),
            ]
        },
    )

    assert recommendations[0].symbol == "KRX:103590"
    assert recommendations[0].state == "우선 검토"
    assert recommendations[0].reflection_penalty == 0
    assert "시세 반영 과도" in " · ".join(recommendations[1].risks)


def test_recommend_signal_candidates_penalizes_bearish_lazy_table():
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
    snapshot = TradingViewTableSnapshot(
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

    recommendations = recommend_signal_candidates(
        [outcome],
        table_snapshots={"KRX:300080": snapshot},
    )

    assert recommendations[0].technical_score == 65
    assert recommendations[0].recommendation_score < 70
    assert "Lazy 테이블 관망/역배열/매도세" in recommendations[0].risks
    assert "진입 보류" in recommendations[0].next_action


def test_recommend_signal_candidates_penalizes_immediate_reentry_flow():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:321370",
        market="KR",
        signal_date="2026-05-24",
        first_signal_date="2026-05-24",
        last_signal_date="2026-05-24",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=3975,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    recommendations = recommend_signal_candidates(
        [outcome],
        label_flows={
            "KRX:321370": [
                TradingViewLabelFlowItem("2026-05-22", "💣 돌파 청산", 10),
                TradingViewLabelFlowItem("2026-05-23", "🛠️ 셋업 형성 중", 11),
                TradingViewLabelFlowItem("2026-05-24", "🚀 돌파 진입", 12),
            ]
        },
    )

    assert recommendations[0].technical_score == 88
    assert recommendations[0].flow_adjustment == -12
    assert "즉시 재진입 휩쏘 위험" in recommendations[0].risks
    assert "진입 보류" in recommendations[0].next_action


def test_format_recommendation_report_is_actionable_telegram_card():
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

    text = format_recommendation_report(
        recommend_signal_candidates([outcome]),
        scanned=12,
        errors=[],
        ticker_cache=[{"code": "103590", "name": "일진전기", "market": "KOSPI"}],
    )

    assert "🎯 시세 반영 전 추천 후보" in text
    assert "목적: 활성 매수 라벨 중 이미 많이 오른 종목보다" in text
    assert "1. KRX:103590 · 일진전기" in text
    assert "추천점수:" in text
    assert "다음 행동:" in text
    assert "symbol |" not in text


def test_empty_recommendation_report_explains_errors_and_exclusions():
    exclusion = TradingViewExcludedSignal(
        symbol="NASDAQ:AAPL",
        market="US",
        signal_date="2026-05-20",
        label="💰 진입",
        exit_date="2026-05-24",
        exit_label="💸 최종 청산",
        entry_bar_index=100,
        exit_bar_index=104,
        risk_flags=[],
        score_penalty_hint=0,
    )

    text = format_recommendation_report(
        [],
        scanned=2,
        errors=[("AMEX:BMNR", "symbol not found")],
        exclusions=[exclusion],
        cooldown_skips=["NASDAQ:MSFT"],
    )

    assert "표시할 추천 후보가 없습니다." in text
    assert "진단: 오류 1건 · 제외 1건 · 활성 매수 후보 0건" in text
    assert "오류 심볼: AMEX:BMNR" in text
    assert "쿨다운 제외: NASDAQ:MSFT" in text
    assert "제외 사유: 💸 최종 청산 1건" in text
    assert "다음 확인: /추천 us 10 동기화" in text
    assert "\n오류: AMEX:BMNR" not in text


def test_build_signal_enrichments_adds_manual_verify_for_us_and_jp_candidates():
    us = TradingViewLabelOutcome(
        symbol="NASDAQ:AAPL",
        market="US",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=190,
        returns={},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    jp = TradingViewLabelOutcome(
        symbol="TSE:7203",
        market="JP",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=3000,
        returns={},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )

    enrichments = build_signal_enrichments(
        [us, jp],
        supply_lookup=lambda ticker: {},
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {},
    )

    assert "EDGAR" in enrichments["NASDAQ:AAPL"].auditor
    assert "EDINET" in enrichments["TSE:7203"].auditor
    assert enrichments["NASDAQ:AAPL"].supply_score is None
    assert enrichments["NASDAQ:AAPL"].independence_alert.startswith("🟡 독립성 확인 필요")


def test_us_recommendation_report_includes_manual_independence_context():
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
    enrichments = build_signal_enrichments(
        [outcome],
        supply_lookup=lambda ticker: {},
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {},
    )

    text = format_recommendation_report(
        recommend_signal_candidates([outcome], enrichments=enrichments),
        scanned=1,
        errors=[],
        table_snapshots={
            "NASDAQ:AAPL": TradingViewTableSnapshot(
                signal="🟢 매수 진입",
                conviction="🟢 A",
                smart_eval="📈 안정적 우상향",
                ema_alignment="🟢 정배열",
                aux_score=65,
                aux_signal="Sigma:PB",
                market_sector="Technology · Consumer Electronics",
                trend_energy="🔥 상승 가속",
                market_control="🐂 매수세",
                rs_score=92,
                volume_strength=1.8,
                high_52w_pct=-8.1,
                stop_loss=172,
                stop_loss_pct=-9.4,
                target_price=228,
                target_return_pct=20,
                risk_reward="2.1",
                buy_eligibility="🟢 적합",
                fundamental="☀️ 펀더멘털: 우수",
                eps_growth=[],
                sales_growth=[],
                raw_rows=[],
            )
        },
    )

    assert "NASDAQ:AAPL" in text
    assert "시장확인: 미국 후보는 EDGAR/10-K 원천 확인 전 매입 보류" in text
    assert "추천점수:" in text
    assert "상태: 원천확인 대기" in text
    assert "다음 행동: 독립성 원천 확인 전 매입 보류" in text
    assert "독립성알림: 🟡 독립성 확인 필요 — 원천 확인 전 매입 보류" in text
    assert "감사인: 수동 확인 필요 · 미국 종목 감사인 자동 확인 미지원. EDGAR/10-K 등 원천 확인 필요." in text
    assert "수급: 시장: 미국 · 거래소 NASDAQ · 수급 자동 미지원" in text
    assert "프로필: 원천: EDGAR/10-K · 감사인/사업/리스크 수동 확인 필요" in text
    assert "Lazy 시장: Technology · Consumer Electronics · 🔥 상승 가속 · 🐂 매수세" in text


def test_jp_recommendation_report_includes_edinet_manual_context():
    outcome = TradingViewLabelOutcome(
        symbol="TSE:7203",
        market="JP",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="💰 진입",
        entry_price=3000,
        returns={"5d": None, "10d": None, "20d": None},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    enrichments = build_signal_enrichments(
        [outcome],
        supply_lookup=lambda ticker: {},
        fundamental_lookup=lambda ticker: {},
        audit_lookup=lambda ticker: {},
    )

    text = format_recommendation_report(
        recommend_signal_candidates([outcome], enrichments=enrichments),
        scanned=1,
        errors=[],
    )

    assert "TSE:7203" in text
    assert "시장확인: 일본 후보는 EDINET/유가증권보고서 원천 확인 전 매입 보류" in text
    assert "상태: 원천확인 대기" in text
    assert "다음 행동: 독립성 원천 확인 전 매입 보류" in text
    assert "수급: 시장: 일본 · 거래소 TSE · 수급 자동 미지원" in text
    assert "프로필: 원천: EDINET/유가증권보고서 · 감사인/사업/리스크 수동 확인 필요" in text
    assert "감사인: 수동 확인 필요 · 일본 종목 감사인 자동 확인 미지원. EDINET/유가증권보고서 등 원천 확인 필요." in text
