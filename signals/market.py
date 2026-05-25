"""Market classification for TradingView symbols."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    code: str
    label: str


def classify_market(ticker: str, exchange: str) -> Market:
    ex = (exchange or "").upper()
    if ex in {"KRX", "KOSPI", "KOSDAQ", "KONEX"} or (
        ticker.isdigit() and len(ticker) == 6
    ):
        return Market("KR", "한국")
    if ex in {"NASDAQ", "NYSE", "AMEX", "ARCA", "BATS", "OTC"}:
        return Market("US", "미국")
    if ex in {"TSE", "TYO", "JPX"}:
        return Market("JP", "일본")
    return Market("UNKNOWN", "미분류")

