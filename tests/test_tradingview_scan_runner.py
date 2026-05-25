import json
from pathlib import Path

from signals.tradingview_scan_runner import (
    build_kr_signal_enrichments,
    format_scan_report,
    format_telegram_outcome_cards,
    market_for_symbol,
    normalize_scan_symbol,
    priority_sort_key,
    symbol_display_name,
    symbols_from_universe,
)
from signals.tradingview_direct import TradingViewLabelOutcome


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
    assert "이후 흐름: 5일 +3.35%" in text


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

    assert "수급: 기관 오늘 +1억 / 5일 -3억 · 외국인 오늘 0억 / 5일 +9억" in text
    assert "실적/밸류: 매출 2025 13,000억 · 영업익 +1,500억 · PER 18.20x · PBR 2.10x" in text
    assert "감사인: 현재연도 감사인 확인 필요 · 삼정회계법인" in text
    assert "2026 감사인 직접 확인 없음" in text
