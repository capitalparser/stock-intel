"""Catalyst layer: per-ticker time-axis events.

KR tickers use DART supply-contract disclosures from the last 90 days.
US tickers use yfinance's upcoming earnings date. Provider failures degrade
to an empty list so one missing source never breaks dashboard rendering.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta

import requests

from dashboard.providers.base import classify_market
from data.fundamental import find_corp_code

_DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
_DART_CAP_GAP = "공급계약 100건 초과 — 최신만"

logger = logging.getLogger(__name__)


def _days_until(date_str: str, today: str) -> int:
    d = date.fromisoformat(date_str)
    t = date.fromisoformat(today)
    return (d - t).days


def _supply_contract_catalysts(dart_list: list[dict], today: str) -> list[dict]:
    rows = [row for row in dart_list if "공급계약" in str(row.get("report_nm", ""))]
    rows.sort(key=lambda row: str(row.get("rcept_dt", "")), reverse=True)

    out: list[dict] = []
    for row in rows:
        raw = str(row.get("rcept_dt", ""))
        if not re.fullmatch(r"\d{8}", raw):
            continue
        try:
            disclosed = _fmt_yyyymmdd(raw)
            elapsed = -_days_until(disclosed, today)
        except ValueError:
            continue
        out.append(
            {
                "type": "supply_contract",
                "direction": "recent",
                "date": disclosed,
                "days": elapsed,
                "label": f"공급계약 ({int(disclosed[5:7])}/{int(disclosed[8:10])})",
                "detail": str(row.get("flr_nm", "")),
            }
        )
    return out


def fetch_catalysts(
    ticker: str,
    market: str | None = None,
    *,
    today: str | None = None,
) -> list[dict]:
    resolved_today = today or date.today().isoformat()
    resolved_market = market or classify_market(ticker)
    if resolved_market == "KR":
        return _fetch_kr_supply_contracts(ticker, resolved_today)
    return _fetch_us_earnings(ticker, resolved_today)


def _fetch_kr_supply_contracts(ticker: str, today: str) -> list[dict]:
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        return []
    try:
        corp_code = find_corp_code(api_key, ticker)
        if not corp_code:
            return []
        response = requests.get(
            _DART_LIST_URL,
            params={
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bgn_de": _minus_days(today, 90),
                "end_de": today.replace("-", ""),
                "page_count": 100,
            },
            timeout=20,
        )
        data = response.json()
        if data.get("status") != "000":
            return []
        catalysts = _supply_contract_catalysts(data.get("list") or [], today)
        if _int_or_zero(data.get("total_count")) > 100:
            logger.warning("%s: %s", ticker, _DART_CAP_GAP)
            for item in catalysts:
                item["data_gap"] = _DART_CAP_GAP
        return catalysts
    except Exception:
        logger.exception("catalyst fetch failed for KR ticker %s", ticker)
        return []


def _fetch_us_earnings(ticker: str, today: str) -> list[dict]:
    try:
        import yfinance as yf

        calendar = yf.Ticker(ticker).calendar
        earnings_date = _extract_earnings_date(calendar)
        if not earnings_date:
            return []
        days = _days_until(earnings_date, today)
        if days < 0:
            return []
        return [
            {
                "type": "earnings",
                "direction": "upcoming",
                "date": earnings_date,
                "days": days,
                "label": f"실적 D-{days}",
                "detail": "",
            }
        ]
    except Exception:
        logger.exception("catalyst fetch failed for US ticker %s", ticker)
        return []


def _extract_earnings_date(calendar) -> str | None:
    # yfinance 1.x: `.calendar` is dict-like; "Earnings Date" can be a date/Timestamp list.
    try:
        value = calendar.get("Earnings Date") if isinstance(calendar, dict) else None
        if not value:
            return None
        first = value[0] if isinstance(value, (list, tuple)) else value
        if isinstance(first, datetime):
            return first.date().isoformat()
        if isinstance(first, date):
            return first.isoformat()
        return date.fromisoformat(str(first)[:10]).isoformat()
    except Exception:
        return None


def _fmt_yyyymmdd(value: str) -> str:
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"


def _minus_days(today: str, days: int) -> str:
    return (date.fromisoformat(today) - timedelta(days=days)).strftime("%Y%m%d")


def _int_or_zero(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
