"""Market classification for TradingView symbols."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    code: str
    label: str


def classify_market(ticker: str, exchange: str) -> Market:
    ex = (exchange or "").upper()
    normalized_ticker = ticker_for_lookup(ticker, "KR")
    if (
        ex in {"KRX", "KOSPI", "KOSDAQ", "KONEX"}
        or ticker.upper().startswith(("KRX:", "KOSPI:", "KOSDAQ:", "KONEX:"))
        or (normalized_ticker.isdigit() and len(normalized_ticker) == 6)
    ):
        return Market("KR", "한국")
    if ex in {"NASDAQ", "NYSE", "AMEX", "ARCA", "BATS", "OTC"}:
        return Market("US", "미국")
    if ex in {"TSE", "TYO", "JPX"}:
        return Market("JP", "일본")
    return Market("UNKNOWN", "미분류")


def ticker_for_lookup(ticker: str, market_code: str) -> str:
    if market_code == "KR":
        return ticker.split(":", 1)[1] if ":" in ticker else ticker
    return ticker


def supports_audit_lookup(ticker: str, market_code: str) -> bool:
    lookup_ticker = ticker_for_lookup(ticker, market_code)
    return market_code == "KR" and lookup_ticker.isdigit() and len(lookup_ticker) == 6
