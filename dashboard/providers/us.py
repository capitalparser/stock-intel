"""US provider via yfinance (free, no API key).

yfinance is imported lazily so the package loads in environments without it
(e.g. the test sandbox); tests monkeypatch ``_load_ticker`` to inject fixtures.
"""

from __future__ import annotations

from dashboard.providers.base import (
    RawStock,
    bollinger_pct_b,
    day_change_pct,
    ma_alignment,
    trailing_return_pct,
    volume_ratio,
)


def fetch_us_stock(ticker: str) -> RawStock:
    raw = RawStock(ticker=ticker, source="US")
    try:
        info, closes, volumes, last_date = _load_ticker(ticker)
    except Exception as exc:  # pragma: no cover - network/optional dep
        raw.errors.append(f"yfinance: {type(exc).__name__}")
        return raw

    _apply_info(raw, info or {})
    _apply_history(raw, closes or [], volumes or [])
    raw.as_of = last_date
    return raw


def _apply_info(raw: RawStock, info: dict) -> None:
    raw.pe = _pos(info.get("trailingPE"))
    raw.pbr = _pos(info.get("priceToBook"))
    om = info.get("operatingMargins")
    if om is not None:
        raw.op_margin_pct = float(om) * 100
    roe = info.get("returnOnEquity")
    if roe is not None:
        raw.roe_pct = float(roe) * 100
    rg = info.get("revenueGrowth")
    if rg is not None:
        raw.revenue_growth_pct = float(rg) * 100
    eg = info.get("earningsGrowth")
    if eg is not None:
        raw.op_growth_pct = float(eg) * 100
    fcf = info.get("freeCashflow")
    ocf = info.get("operatingCashflow")
    flow = ocf if ocf is not None else fcf
    if flow is not None:
        raw.ocf_positive = float(flow) > 0


def _apply_history(raw: RawStock, closes: list[float], volumes: list[float]) -> None:
    if not closes:
        return
    raw.closes = [float(c) for c in closes[-60:] if c is not None]
    raw.price = float(closes[-1])
    raw.day_change_pct = day_change_pct(closes)
    raw.return_pct = trailing_return_pct(closes, lookback=21)
    raw.bb_pct = bollinger_pct_b(closes)
    raw.ma_trend = ma_alignment(closes)
    if volumes:
        raw.volume_ratio = volume_ratio(volumes)
    # US flow/short not sourced here -> net_flow_signal stays None.


def _load_ticker(ticker: str) -> tuple[dict, list[float], list[float], str | None]:
    """Return (info, closes, volumes, last_date). Patched in tests."""
    import yfinance as yf  # lazy

    t = yf.Ticker(ticker)
    try:
        info = dict(t.info)
    except Exception:
        info = {}
    hist = t.history(period="9mo", interval="1d")
    closes: list[float] = []
    volumes: list[float] = []
    last_date: str | None = None
    if hist is not None and not hist.empty:
        closes = [float(v) for v in hist["Close"].tolist() if v == v]
        if "Volume" in hist.columns:
            volumes = [float(v) for v in hist["Volume"].tolist() if v == v]
        last_date = hist.index[-1].strftime("%Y-%m-%d")
    return info, closes, volumes, last_date


def _pos(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None
