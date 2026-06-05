"""Audit-independence overlay for dashboard candidates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from data.audit_firm import fetch_audit_firm
from dashboard.providers.base import classify_market
from signals.independence import decide_independence
from signals.market import Market, ticker_for_lookup

_BLOCKED = {"BLOCKED_CONFIRMED", "BLOCKED_POSSIBLE"}
_MANUAL = {
    "MANUAL_VERIFY",
    "MANUAL_VERIFY_CURRENT_YEAR",
    "ROLLOVER_INFERRED",
    "DATA_MISSING",
    "UNKNOWN_MARKET",
}

_BLOCKED_LABELS = {
    "BLOCKED_CONFIRMED": "🚫 독립성 차단 — 매입 검토 금지",
    "BLOCKED_POSSIBLE": "🚫 독립성 차단 가능 — 원천 확인 전 보류",
}


def independence_flag(status: str | None, market: str | None = None) -> tuple[str | None, bool]:
    """Map an independence status to a risk flag and blocked boolean."""
    if _is_non_kr_market(market):
        return "🟡 독립성 확인 필요", False
    if status in _BLOCKED:
        return _BLOCKED_LABELS[str(status)], True
    if status in _MANUAL:
        return "🟡 독립성 확인 필요", False
    return None, False


def fetch_independence(
    tickers: str | Iterable[str | Mapping[str, Any]],
    *,
    as_of_year: int | None = None,
) -> dict:
    """Return audit-independence decisions for one ticker or a batch of tickers.

    A single string returns one decision dict for compatibility with snapshot
    call sites. An iterable returns ``{ticker: decision}``.
    """
    if isinstance(tickers, str):
        return _fetch_one(tickers, as_of_year=as_of_year)
    return {
        ticker: _fetch_one(ticker, market=market, as_of_year=as_of_year)
        for ticker, market in (_normalize_item(item) for item in tickers)
    }


def _fetch_one(
    ticker: str,
    *,
    market: str | None = None,
    as_of_year: int | None = None,
) -> dict[str, str | None]:
    market_code, market_label = _market_parts(ticker, market)
    if market_code not in {"KR", "한국"}:
        return {
            "status": "MANUAL_VERIFY",
            "auditor": None,
            "reason": f"Market({market_code},{market_label})→MANUAL_VERIFY",
        }

    lookup_ticker = ticker_for_lookup(ticker, "KR")
    try:
        audit = fetch_audit_firm(lookup_ticker)
    except Exception as exc:  # pragma: no cover - defensive degrade
        audit = {"error": f"감사인 조회 실패: {type(exc).__name__}"}
    decision = decide_independence(Market("KR", "한국"), audit, as_of_year=as_of_year)
    return {
        "status": decision.status,
        "auditor": decision.auditor,
        "reason": decision.reason,
    }


def _normalize_item(item: str | Mapping[str, Any]) -> tuple[str, str | None]:
    if isinstance(item, str):
        return item, None
    ticker = str(item.get("ticker") or item.get("symbol") or "")
    market = item.get("market") or item.get("source")
    return ticker, None if market is None else str(market)


def _market_parts(ticker: str, market: str | None) -> tuple[str, str]:
    raw_market = (market or "").strip()
    if raw_market:
        if raw_market == "한국":
            return "KR", "한국"
        if raw_market == "미국":
            return "US", "미국"
        upper = raw_market.upper()
        if upper == "KR":
            return "KR", "한국"
        if upper == "US":
            return "US", "미국"
        return upper, raw_market

    market_code = classify_market(ticker)
    if market_code == "KR":
        return "KR", "한국"
    return market_code, "미국" if market_code == "US" else market_code


def _is_non_kr_market(market: str | None) -> bool:
    if not market:
        return False
    normalized = market.strip().upper()
    return normalized not in {"KR", "한국"}
