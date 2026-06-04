"""Macro provider: market indicators + a derived regime read via yfinance.

Replaces the hardcoded ``market_indicators`` / ``regime`` blocks. Produces
payloads shaped exactly like the dashboard models so ``live.py`` can drop them
straight into the input. yfinance is lazily imported; ``_load_quotes`` is
patched in tests.
"""

from __future__ import annotations

from dashboard.macro_state import build_macro_state
from dashboard.providers.base import day_change_pct, trailing_return_pct

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
    """Return ``{"market_indicators": [...], "regime": {...}, "errors": [...]}``.

    Any symbol that fails to load is skipped from the strip; the regime falls
    back to a neutral "conditional" read when key inputs are missing.
    """
    errors: list[str] = []
    symbols = sorted({s for s, _, _ in INDICATOR_SYMBOLS} | set(REGIME_SYMBOLS))
    try:
        quotes = _load_quotes(symbols)
    except Exception as exc:  # pragma: no cover - network/optional dep
        return {"market_indicators": [], "regime": {}, "errors": [f"macro: {type(exc).__name__}"]}

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

    regime = _derive_regime(quotes)
    macro_state = build_macro_state(
        {
            "market_indicators": indicators,
            "issues": _default_issue_cards(),
        }
    )
    return {
        "market_indicators": indicators,
        "regime": regime,
        "macro_state": macro_state,
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


def _default_issue_cards() -> list[dict]:
    return [
        {
            "theme": "지정학",
            "title": "중동 휴전 기대와 현장 충돌의 괴리",
            "state": "unresolved",
            "summary": "협상 기대는 남아 있으나 유가·금리·변동성이 종전 신뢰도를 확인해야 하는 상태.",
            "triggers": ["Brent 95달러 위 고착", "미 10년물 4.5% 재상승", "VIX 동반 상승"],
            "source_gaps": ["실시간 뉴스 자동 요약 미연결"],
        }
    ]


def _derive_regime(quotes: dict) -> dict:
    vix = _price(quotes, "^VIX")
    tnx = _price(quotes, "^TNX")
    tnx_chg = _chg(quotes, "^TNX")
    dxy_chg = _chg(quotes, "DX-Y.NYB")
    spy_ret = _ret(quotes, "SPY")

    volatility = "low" if vix is not None and vix < 16 else (
        "elevated" if vix is not None and vix < 22 else (
            "high" if vix is not None else "unknown"
        )
    )
    risk_appetite = "risk-on" if (spy_ret or 0) > 0 else (
        "risk-off" if (spy_ret or 0) < -3 else "neutral"
    )
    rates = "rising" if (tnx_chg or 0) > 1.5 else (
        "falling" if (tnx_chg or 0) < -1.5 else "stable"
    )
    dollar = "strong" if (dxy_chg or 0) > 0.3 else (
        "weak" if (dxy_chg or 0) < -0.3 else "stable"
    )

    if volatility == "high" or (spy_ret is not None and spy_ret < -5):
        verdict = "risk-off"
    elif volatility == "low" and risk_appetite == "risk-on":
        verdict = "risk-on"
    else:
        verdict = "conditional"

    notes: list[str] = []
    if vix is not None:
        notes.append(f"VIX {vix:.1f} ({volatility}).")
    if tnx is not None:
        notes.append(f"미 10년물 {tnx:.2f}% ({rates}).")
    if spy_ret is not None:
        notes.append(f"S&P 직전 ~1개월 {spy_ret:+.1f}%.")
    if not notes:
        notes.append("매크로 실데이터 미연결 — 중립 가정.")

    return {
        "verdict": verdict,
        "risk_appetite": risk_appetite,
        "rates": rates,
        "dollar": dollar,
        "volatility": volatility,
        "notes": notes,
    }


def _price(quotes: dict, sym: str) -> float | None:
    q = quotes.get(sym)
    return q.get("price") if q else None


def _chg(quotes: dict, sym: str) -> float | None:
    q = quotes.get(sym)
    return q.get("day_change_pct") if q else None


def _ret(quotes: dict, sym: str) -> float | None:
    q = quotes.get(sym)
    return q.get("return_pct") if q else None


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
