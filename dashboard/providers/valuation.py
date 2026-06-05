"""Valuation provider: yfinance .info forward fields -> expectation verdict."""

from __future__ import annotations

from typing import Any

from dashboard.providers.base import classify_market
from dashboard.valuation_expectations import expectation_verdict

_CORE_FIELDS = ("forwardPE", "revenueGrowth", "earningsGrowth")


def fetch_valuation(ticker: str) -> dict:
    base = {"ticker": ticker}
    info = _fetch_info(ticker)

    forward_pe = _positive_float(info.get("forwardPE"))
    rev_growth_pct = _pct(info.get("revenueGrowth"))
    eps_growth_pct = _pct(info.get("earningsGrowth"))
    fcf_margin_pct = _fcf_margin(info, forward_pe)
    verdict = expectation_verdict(
        forward_pe=forward_pe,
        rev_growth_pct=rev_growth_pct,
        eps_growth_pct=eps_growth_pct,
        fcf_margin_pct=fcf_margin_pct,
    )
    return {
        **base,
        "forward_pe": round(forward_pe, 1) if forward_pe is not None else None,
        "rev_growth_pct": round(rev_growth_pct, 1) if rev_growth_pct is not None else None,
        "eps_growth_pct": round(eps_growth_pct, 1) if eps_growth_pct is not None else None,
        "fcf_margin_pct": round(fcf_margin_pct, 1) if fcf_margin_pct is not None else None,
        "analyst_n": info.get("numberOfAnalystOpinions"),
        "recommendation": info.get("recommendationKey"),
        **verdict,
    }


def _fetch_info(ticker: str) -> dict[str, Any]:
    try:
        import yfinance as yf
    except Exception:
        return {}

    for symbol in _candidate_symbols(ticker):
        info = _info_for_symbol(yf, symbol)
        if _has_core_fields(info):
            return info
    return {}


def _candidate_symbols(ticker: str) -> list[str]:
    if classify_market(ticker) == "KR":
        return [f"{ticker}.KS", f"{ticker}.KQ"]
    return [ticker]


def _info_for_symbol(yf, symbol: str) -> dict[str, Any]:
    try:
        return dict(yf.Ticker(symbol).info or {})
    except Exception:
        return {}


def _has_core_fields(info: dict[str, Any]) -> bool:
    return any(info.get(field) is not None for field in _CORE_FIELDS)


def _fcf_margin(info: dict[str, Any], forward_pe: float | None) -> float | None:
    fcf = info.get("freeCashflow")
    total_revenue = info.get("totalRevenue")
    if fcf is not None and total_revenue not in (None, 0) and forward_pe is not None and forward_pe > 0:
        return float(fcf) / float(total_revenue) * 100
    return None


def _pct(value) -> float | None:
    if value is None:
        return None
    return float(value) * 100


def _positive_float(value) -> float | None:
    if value is None:
        return None
    out = float(value)
    if out <= 0:
        return None
    return out
