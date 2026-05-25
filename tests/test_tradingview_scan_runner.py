import json
from pathlib import Path

from signals.tradingview_scan_runner import (
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
    assert "1. NASDAQ:AAPL" in text
    assert "라벨: 💰 진입" in text
    assert "수익률: 5일 +3.35%" in text


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

    assert "1. KRX:103590 · 일진전기" in text


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
