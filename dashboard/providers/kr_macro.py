"""KR macro indicators for the dual-regime engine.

KRX OPEN API(authoritative index data) plus yfinance proxies are shaped into
the indicator list consumed by build_market_regime. Tests can inject quotes to
avoid network access. Flow uses EWY as a proxy, not actual foreign net buying.
"""

from __future__ import annotations

import math
from typing import Any

from dashboard.providers.base import day_change_pct


def realized_vol(closes: list[float], window: int = 20) -> float:
    use = [float(c) for c in closes[-(window + 1):] if c is not None]
    if len(use) < 3:
        return 0.0
    rets = [use[i] / use[i - 1] - 1 for i in range(1, len(use))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(var) * math.sqrt(252) * 100


def relative_strength(numerator: list[float], denominator: list[float], window: int = 20) -> float:
    """Relative strength of numerator vs denominator, scaled 0..100."""

    def ret(series: list[float]) -> float:
        use = [float(c) for c in series if c is not None]
        if len(use) <= window:
            return 0.0
        return use[-1] / use[-window - 1] - 1

    spread = ret(numerator) - ret(denominator)
    return max(0.0, min(100.0, 50.0 + spread * 1000))


def _rv_series(closes: list[float], window: int = 20) -> list[float]:
    out = []
    for end in range(window + 1, len(closes) + 1):
        out.append(realized_vol(closes[:end], window))
    return out


def _rs_series(numerator: list[float], denominator: list[float], window: int = 20) -> list[float]:
    n = min(len(numerator), len(denominator))
    out = []
    for end in range(window + 1, n + 1):
        out.append(relative_strength(numerator[:end], denominator[:end], window))
    return out


def build_kr_indicators(*, quotes: dict[str, Any]) -> list[dict]:
    inds: list[dict] = []
    kospi = quotes.get("KOSPI") or {}
    kosdaq = quotes.get("KOSDAQ") or {}
    usdkrw = quotes.get("USDKRW=X") or {}
    ewy = quotes.get("EWY") or {}

    kospi_closes = kospi.get("closes") or []
    if kospi_closes:
        inds.append(
            {
                "symbol": "KOSPI",
                "value": kospi_closes[-1],
                "series": kospi_closes,
                "day_change_pct": kospi.get("day_change_pct", 0.0),
            }
        )
        rv = _rv_series(kospi_closes)
        if rv:
            inds.append(
                {"symbol": "KOSPI_RV", "value": rv[-1], "series": rv, "day_change_pct": 0.0}
            )

    kosdaq_closes = kosdaq.get("closes") or []
    if kosdaq_closes and kospi_closes:
        rs = _rs_series(kosdaq_closes, kospi_closes)
        if rs:
            inds.append(
                {
                    "symbol": "KOSPI_BREADTH",
                    "value": rs[-1],
                    "series": rs,
                    "day_change_pct": 0.0,
                }
            )

    usdkrw_closes = usdkrw.get("closes") or []
    if usdkrw_closes:
        inds.append(
            {
                "symbol": "USDKRW=X",
                "value": usdkrw.get("value", usdkrw_closes[-1]),
                "series": usdkrw_closes,
                "day_change_pct": 0.0,
            }
        )

    ewy_closes = ewy.get("closes") or []
    if ewy_closes:
        inds.append(
            {
                "symbol": "FOREIGN_NET",
                "value": ewy.get("value", ewy_closes[-1]),
                "series": ewy_closes,
                "day_change_pct": 0.0,
                "source_kind": "proxy",
                "read": "EWY 프록시 — 실제 외국인 순매수 아님",
            }
        )
    return inds


def fetch_kr_quotes() -> dict[str, Any]:
    """Fetch KR macro proxy quotes via yfinance only.

    KOSPI/KOSDAQ are liquid ETF proxies. KRX/yfinance index tickers such as
    ^KS11 and ^KS200 are intentionally not used because they can return NaN.
    """

    import yfinance as yf  # lazy

    symbols = {
        "KOSPI": "069500.KS",
        "KOSDAQ": "229200.KS",
        "USDKRW=X": "USDKRW=X",
        "EWY": "EWY",
    }
    out: dict[str, Any] = {}
    for key, yf_symbol in symbols.items():
        try:
            data = yf.download(yf_symbol, period="1y", interval="1d", progress=False)
            closes = [float(v) for v in data["Close"].dropna().tolist()]
        except Exception:
            continue
        closes = [c for c in closes if math.isfinite(c)]
        if not closes:
            continue
        out[key] = {
            "closes": closes,
            "day_change_pct": day_change_pct(closes),
            "value": closes[-1],
        }
    return out
