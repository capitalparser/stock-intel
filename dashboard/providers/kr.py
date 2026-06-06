"""KR provider: wrap the existing synchronous ``data/`` layer into RawStock.

Reuses the same fetchers the Telegram bot already relies on
(``fetch_fundamental``, ``fetch_technical``, ``fetch_supply``,
``fetch_short_sell``) so the dashboard and the bot share one source of truth
for Korean names. pykrx is used directly only for price/day-change/return,
which the existing fetchers do not expose.
"""

from __future__ import annotations

import io
import logging
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta

from dashboard.providers.base import (
    RawStock,
    day_change_pct,
    trailing_return_pct,
)


def fetch_kr_stock(ticker: str) -> RawStock:
    raw = RawStock(ticker=ticker, source="KR")

    fundamental = _safe(lambda: _import_fund()(ticker), raw, "fundamental")
    technical = _safe(lambda: _import_tech()(ticker), raw, "technical")
    supply = _safe(lambda: _import_supply()(ticker), raw, "supply")
    short = _safe(lambda: _import_short()(ticker), raw, "short_sell")

    _apply_fundamental(raw, fundamental)
    _apply_technical(raw, technical)
    _apply_supply(raw, supply)
    _apply_short(raw, short)
    _apply_price_series(raw, technical)

    return raw


# --- lazy imports so the package imports without pykrx present -------------- #
def _import_fund():
    from data.fundamental import fetch_fundamental

    return fetch_fundamental


def _import_tech():
    from data.technical import fetch_technical

    return fetch_technical


def _import_supply():
    from data.supply import fetch_supply

    return fetch_supply


def _import_short():
    from data.short_sell import fetch_short_sell

    return fetch_short_sell


def _safe(fn, raw: RawStock, label: str):
    try:
        result = fn()
    except Exception as exc:  # pragma: no cover - defensive
        raw.errors.append(f"{label}: {type(exc).__name__}")
        return None
    if isinstance(result, dict) and result.get("error"):
        raw.errors.append(f"{label}: {result['error']}")
        return None
    return result


def _apply_fundamental(raw: RawStock, data: dict | None) -> None:
    if not data:
        return
    ratios = data.get("ratios") or {}
    per = ratios.get("per")
    pbr = ratios.get("pbr")
    raw.pe = float(per) if per else None
    raw.pbr = float(pbr) if pbr else None
    if ratios.get("date"):
        raw.as_of = ratios["date"]

    financials = data.get("financials") or []
    if financials:
        latest = financials[-1]
        revenue = latest.get("revenue")
        op = latest.get("operating_income")
        ocf = latest.get("operating_cash_flow")
        if revenue and op is not None and revenue != 0:
            raw.op_margin_pct = op / revenue * 100
        if ocf is not None:
            raw.ocf_positive = ocf > 0
    if len(financials) >= 2:
        prev, last = financials[-2], financials[-1]
        raw.revenue_growth_pct = _yoy(prev.get("revenue"), last.get("revenue"))
        raw.op_growth_pct = _yoy(prev.get("operating_income"), last.get("operating_income"))


def _apply_technical(raw: RawStock, data: dict | None) -> None:
    if not data:
        return
    if raw.price is None and data.get("price") is not None:
        raw.price = float(data["price"])
    raw.bb_pct = _opt_float(data.get("bb_pct"))
    raw.volume_ratio = _opt_float(data.get("volume_ratio"))
    raw.ma_trend = data.get("ma_trend") or None
    if not raw.as_of and data.get("date"):
        raw.as_of = data["date"]


def _apply_supply(raw: RawStock, data: dict | None) -> None:
    if not data:
        return
    inst = (data.get("institution") or {}).get("today")
    frgn = (data.get("foreigner") or {}).get("today")
    total = sum(v for v in (inst, frgn) if isinstance(v, (int, float)))
    if inst is None and frgn is None:
        return
    if total > 0:
        raw.net_flow_signal = 1.0
    elif total < 0:
        raw.net_flow_signal = -1.0
    else:
        raw.net_flow_signal = 0.0


def _apply_short(raw: RawStock, data: dict | None) -> None:
    if not data:
        return
    raw.short_ratio = _opt_float(data.get("ratio_today"))


def _apply_price_series(raw: RawStock, technical: dict | None) -> None:
    """Best-effort price/day-change/return via pykrx OHLCV.

    Heavily guarded: any failure leaves the (optional) fields as-is.
    """
    closes = _safe_ohlcv_closes(raw.ticker)
    if not closes:
        return
    raw.closes = [float(c) for c in closes[-60:] if c is not None]
    if raw.price is None:
        raw.price = float(closes[-1])
    if raw.day_change_pct is None:
        raw.day_change_pct = day_change_pct(closes)
    if raw.return_pct is None:
        raw.return_pct = trailing_return_pct(closes, lookback=21)


def _safe_ohlcv_closes(ticker: str) -> list[float]:
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from pykrx import stock

            todate = datetime.today().strftime("%Y%m%d")
            fromdate = (datetime.today() - timedelta(days=60)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv_by_date(fromdate, todate, ticker)
        if df is None or df.empty or "종가" not in df.columns:
            return []
        return [float(v) for v in df["종가"].tolist() if v]
    except Exception:  # pragma: no cover - network/optional dep
        return []
    finally:
        logging.disable(previous)


def _yoy(prev, last) -> float | None:
    if prev is None or last is None or prev <= 0:
        return None
    return (last / prev - 1) * 100


def _opt_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
