"""KR macro indicators for the dual-regime engine.

KRX OPEN API(authoritative index data) plus yfinance proxies are shaped into
the indicator list consumed by build_market_regime. Tests can inject quotes to
avoid network access. Flow uses EWY as a proxy, not actual foreign net buying.
"""

from __future__ import annotations

import math
from typing import Any


def realized_vol(closes: list[float], window: int = 20) -> float:
    use = [float(c) for c in closes[-(window + 1):] if c is not None]
    if len(use) < 3:
        return 0.0
    rets = [use[i] / use[i - 1] - 1 for i in range(1, len(use))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(var) * math.sqrt(252) * 100


def relative_strength(kospi: list[float], kospi200: list[float], window: int = 20) -> float:
    """KOSPI vs KOSPI200 relative strength, scaled 0..100."""

    def ret(series: list[float]) -> float:
        use = [float(c) for c in series if c is not None]
        if len(use) <= window:
            return 0.0
        return use[-1] / use[-window - 1] - 1

    spread = ret(kospi) - ret(kospi200)
    return max(0.0, min(100.0, 50.0 + spread * 1000))


def _rv_series(closes: list[float], window: int = 20) -> list[float]:
    out = []
    for end in range(window + 1, len(closes) + 1):
        out.append(realized_vol(closes[:end], window))
    return out


def _rs_series(kospi: list[float], kospi200: list[float], window: int = 20) -> list[float]:
    n = min(len(kospi), len(kospi200))
    out = []
    for end in range(window + 1, n + 1):
        out.append(relative_strength(kospi[:end], kospi200[:end], window))
    return out


def build_kr_indicators(*, quotes: dict[str, Any]) -> list[dict]:
    inds: list[dict] = []
    kospi = quotes.get("KOSPI") or {}
    kospi200 = quotes.get("KOSPI200") or {}
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

    kospi200_closes = kospi200.get("closes") or []
    if kospi_closes and kospi200_closes:
        rs = _rs_series(kospi_closes, kospi200_closes)
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
    """Live quote wiring is deferred until the KRX_API_KEY task."""

    raise NotImplementedError("Task 5에서 KRX+yfinance 라이브 배선")
