import json
from pathlib import Path

import pytest

from signals.market import classify_market, ticker_for_lookup
from signals.pipeline import SignalPipeline
from signals.storage import SignalStore


FIXTURES = Path(__file__).parent / "fixtures"


def load_actual_kr_watchlist() -> dict:
    return json.loads(
        (FIXTURES / "tradingview_watchlist_kr_actual.json").read_text(encoding="utf-8")
    )


def make_payload(symbol: str) -> dict:
    return {
        "schema_version": "v6.2",
        "ticker": symbol,
        "name": symbol,
        "exchange": "",
        "timeframe": "1D",
        "action": "BUY",
        "type": "💰 정석 진입",
        "price": 10000,
        "score": 80,
        "conviction": "A",
    }


def test_actual_tradingview_kr_watchlist_symbols_are_classified_as_korean():
    symbols = load_actual_kr_watchlist()["symbols"]
    equity_symbols = [symbol for symbol in symbols if symbol.removeprefix("KRX:").isdigit()]

    assert len(symbols) == 18
    assert len(equity_symbols) == 17
    assert all(classify_market(symbol, "").code == "KR" for symbol in equity_symbols)


def test_krx_prefixed_ticker_is_normalized_for_audit_lookup():
    assert ticker_for_lookup("KRX:399720", "KR") == "399720"


@pytest.mark.asyncio
async def test_pipeline_uses_actual_kr_watchlist_symbol_for_korean_audit_lookup(tmp_path):
    lookup_tickers: list[str] = []
    sent: list[str] = []

    async def sender(text: str) -> bool:
        sent.append(text)
        return True

    def audit_lookup(ticker: str) -> dict:
        lookup_tickers.append(ticker)
        return {"current_firm": "삼정회계법인"}

    pipeline = SignalPipeline(
        store=SignalStore(tmp_path / "signals.db"),
        audit_lookup=audit_lookup,
        send_message=sender,
    )

    result = await pipeline.handle_payload(make_payload("KRX:399720"))

    assert lookup_tickers == ["399720"]
    assert result.independence_status == "BLOCKED"
    assert sent[0].startswith("🚫 독립성 차단")


@pytest.mark.asyncio
async def test_pipeline_does_not_audit_lookup_actual_kr_non_equity_symbol(tmp_path):
    lookup_tickers: list[str] = []
    sent: list[str] = []

    async def sender(text: str) -> bool:
        sent.append(text)
        return True

    def audit_lookup(ticker: str) -> dict:
        lookup_tickers.append(ticker)
        return {"current_firm": "삼정회계법인"}

    pipeline = SignalPipeline(
        store=SignalStore(tmp_path / "signals.db"),
        audit_lookup=audit_lookup,
        send_message=sender,
    )

    result = await pipeline.handle_payload(make_payload("KRX:S0X1!"))

    assert lookup_tickers == []
    assert result.independence_status == "MANUAL_VERIFY"
    assert sent[0].startswith("🟡 독립성 확인 필요")
