"""Macro provider: market indicators and dual-regime inputs via yfinance.

yfinance is lazily imported; ``_load_quotes`` is patched in tests.
"""

from __future__ import annotations

from dashboard.providers.base import day_change_pct, trailing_return_pct
from dashboard.providers.kr_macro import build_kr_indicators, fetch_kr_quotes

# (symbol, display name, group) for the indicator strip.
INDICATOR_SYMBOLS: list[tuple[str, str, str]] = [
    ("SPY", "S&P 500 ETF", "미국 대형주"),
    ("RSP", "S&P 500 동일가중", "breadth"),
    ("QQQ", "Nasdaq 100 ETF", "성장주"),
    ("IWM", "Russell 2000 ETF", "breadth"),
    ("S5FI", "S&P 500 50일선 상회 비율", "breadth"),
    ("SMH", "Semiconductor ETF", "반도체"),
    ("^VIX", "변동성지수 VIX", "심리"),
    ("^TNX", "미국 10년물", "금리"),
    ("DX-Y.NYB", "달러인덱스", "환율"),
    ("USDKRW=X", "달러/원", "환율"),
    ("GLD", "금 ETF", "원자재"),
    ("BZ=F", "Brent 원유", "유가"),
]

# Extra symbols used only for the regime read (not shown as cards).
REGIME_SYMBOLS = ["^VIX", "^TNX", "DX-Y.NYB", "CL=F", "BZ=F", "SPY", "RSP", "S5FI"]


def fetch_macro() -> dict:
    """Return macro indicator cards plus US/KR dual-regime indicator inputs.

    Any symbol that fails to load is skipped from the strip; downstream
    dual-regime rendering degrades missing axes independently.
    """
    errors: list[str] = []
    symbols = sorted({s for s, _, _ in INDICATOR_SYMBOLS} | set(REGIME_SYMBOLS))
    try:
        quotes = _load_quotes(symbols)
    except Exception as exc:  # pragma: no cover - network/optional dep
        return {
            "market_indicators": [],
            "_us_indicators": [],
            "_kr_indicators": [],
            "errors": [f"macro: {type(exc).__name__}"],
        }

    indicators = []
    for symbol, name, group in INDICATOR_SYMBOLS:
        q = quotes.get(symbol)
        if not q or q.get("price") is None:
            errors.append(f"{symbol}: no data")
            continue
        chg = q.get("day_change_pct")
        indicators.append(
            {
                "symbol": symbol,
                "name": name,
                "group": group,
                "price": round(q["price"], 2),
                "day_change_pct": round(chg, 2) if chg is not None else 0.0,
                "read": _indicator_read(symbol, group, chg),
                "value": round(q["price"], 2),
                "series": q.get("closes") or [],
            }
        )

    kr_indicators: list[dict] = []
    try:
        kr_indicators = build_kr_indicators(quotes=fetch_kr_quotes())
    except Exception as exc:  # pragma: no cover - network/optional dep
        errors.append(f"kr_macro: {type(exc).__name__}")

    return {
        "market_indicators": indicators,
        "_us_indicators": indicators,
        "_kr_indicators": kr_indicators,
        "errors": errors,
    }


def _indicator_read(symbol: str, group: str, chg: float | None) -> str:
    if symbol == "^VIX":
        return "변동성 진정. 위험자산 우호적." if (chg or 0) <= 0 else "변동성 상승. 단기 리스크 점검 필요."
    if chg is None:
        return f"{group} 기준값. 추세 확인 필요."
    if chg >= 0.5:
        return f"{group} 강세. 신규 진입은 후보별 가격 매력 확인 필요."
    if chg <= -0.5:
        return f"{group} 약세. 방어적 접근."
    return f"{group} 보합. 추세 전환 신호 대기."


def _load_quotes(symbols: list[str]) -> dict[str, dict]:
    """Return ``{symbol: {price, day_change_pct, return_pct}}``. Patched in tests."""
    import yfinance as yf  # lazy

    data = yf.download(
        symbols, period="1y", interval="1d", progress=False, group_by="ticker"
    )
    out: dict[str, dict] = {}
    for sym in symbols:
        try:
            closes = [float(v) for v in data[sym]["Close"].dropna().tolist()]
        except Exception:
            closes = []
        if not closes:
            continue
        out[sym] = {
            "price": closes[-1],
            "day_change_pct": day_change_pct(closes),
            "return_pct": trailing_return_pct(closes, lookback=21),
            "closes": closes,
        }
    return out
