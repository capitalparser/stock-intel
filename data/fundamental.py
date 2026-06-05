"""주요 재무정보 + 펀더멘탈 코멘트.

DART 단일회사 전체 재무제표에서 최근 3개년 매출/영업이익/영업활동현금흐름을,
pykrx에서 PER/PBR/EPS/BPS/DPS/배당수익률을 조회한다.
"""
from __future__ import annotations

import io
import logging
import os
import sqlite3
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

import pandas as pd
import requests
from dotenv import load_dotenv


load_dotenv()

_CACHE_PATH = Path(__file__).parent.parent / "cache" / "dart_corp_codes.xml"
_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
_FINANCIAL_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
_ANNUAL_REPORT_CODE = "11011"


def fetch_fundamental(ticker: str) -> dict:
    """최근 3개년 핵심 재무정보와 주요 투자지표 조회."""
    financials: list[dict] = []
    ratios: dict = {}

    try:
        financials = _fetch_local_financials(ticker)
    except Exception:
        financials = []

    if not financials:
        try:
            financials = _fetch_dart_financials(ticker)
        except Exception:
            financials = []

    try:
        ratios = _fetch_market_ratios(ticker)
    except Exception:
        ratios = {}

    if not financials and not ratios:
        return {"error": "재무 데이터를 가져올 수 없습니다."}

    return {
        "financials": financials,
        "ratios": ratios,
        "comment": _build_fundamental_comment(financials, ratios),
    }


def _fetch_local_financials(ticker: str) -> list[dict]:
    db_path = _sqlite_path_from_db_url(os.getenv("DB_URL"))
    if db_path is None or not db_path.exists():
        return []

    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        corp = con.execute(
            "select corp_code from companies where stock_code = ?",
            (ticker,),
        ).fetchone()
        if corp is None:
            return []

        rows = con.execute(
            """
            select year, fs_div, revenue, operating_profit
            from financials
            where corp_code = ?
              and quarter = 4
              and revenue is not null
            order by year desc,
              case fs_div when 'CFS' then 0 when 'OFS' then 1 else 2 end
            """,
            (corp["corp_code"],),
        ).fetchall()

        by_year: dict[int, sqlite3.Row] = {}
        for row in rows:
            by_year.setdefault(int(row["year"]), row)
            if len(by_year) >= 3:
                break

        output: list[dict] = []
        for year, row in sorted(by_year.items()):
            output.append(
                {
                    "year": year,
                    "revenue": row["revenue"],
                    "operating_income": row["operating_profit"],
                    "operating_cash_flow": _fetch_local_operating_cash_flow(
                        con,
                        corp["corp_code"],
                        year,
                        row["fs_div"],
                    ),
                    "fs_div": row["fs_div"],
                }
            )

    return output


def _sqlite_path_from_db_url(db_url: str | None) -> Path | None:
    if not db_url or not db_url.startswith("sqlite:///"):
        return None
    return Path(unquote(db_url.replace("sqlite:///", "/", 1)))


def _fetch_local_operating_cash_flow(
    con: sqlite3.Connection,
    corp_code: str,
    year: int,
    fs_div: str,
) -> int | None:
    row = con.execute(
        """
        select thstrm_amount
        from financial_facts
        where corp_code = ?
          and bsns_year = ?
          and reprt_code = ?
          and fs_div = ?
          and sj_div = 'CF'
          and replace(account_nm, ' ', '') in (
            '영업활동현금흐름',
            '영업활동으로인한현금흐름'
          )
        order by ord
        limit 1
        """,
        (corp_code, year, _ANNUAL_REPORT_CODE, fs_div),
    ).fetchone()
    if row is None:
        return None
    return _parse_amount(row["thstrm_amount"])


def _fetch_dart_financials(ticker: str) -> list[dict]:
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        return []

    corp_code = find_corp_code(api_key, ticker)
    if not corp_code:
        return []

    current_year = datetime.today().year - 1
    rows: list[dict] = []
    for year in range(current_year, current_year - 5, -1):
        item = _fetch_dart_year(api_key, corp_code, year, "CFS")
        if item is None:
            item = _fetch_dart_year(api_key, corp_code, year, "OFS")
        if item is not None:
            rows.append(item)
        if len(rows) >= 3:
            break

    return sorted(rows, key=lambda row: row["year"])


def find_corp_code(api_key: str, ticker: str) -> str | None:
    xml_bytes = _load_corp_code_xml(api_key)
    root = ElementTree.fromstring(xml_bytes)
    for item in root.findall("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        if stock_code == ticker:
            return (item.findtext("corp_code") or "").strip() or None
    return None


def _find_corp_code(api_key: str, ticker: str) -> str | None:
    return find_corp_code(api_key, ticker)


def _load_corp_code_xml(api_key: str) -> bytes:
    if _CACHE_PATH.exists():
        age = datetime.now() - datetime.fromtimestamp(_CACHE_PATH.stat().st_mtime)
        if age < timedelta(days=7):
            return _CACHE_PATH.read_bytes()

    response = requests.get(_CORP_CODE_URL, params={"crtfc_key": api_key}, timeout=20)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        xml_bytes = zf.read("CORPCODE.xml")

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_bytes(xml_bytes)
    return xml_bytes


def _fetch_dart_year(
    api_key: str,
    corp_code: str,
    year: int,
    fs_div: str,
) -> dict | None:
    response = requests.get(
        _FINANCIAL_URL,
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": _ANNUAL_REPORT_CODE,
            "fs_div": fs_div,
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "000":
        return None

    accounts = data.get("list") or []
    revenue = _pick_amount(accounts, ("매출액", "수익(매출액)", "영업수익"))
    operating_income = _pick_amount(accounts, ("영업이익",))
    operating_cash_flow = _pick_amount(
        accounts,
        (
            "영업활동현금흐름",
            "영업활동으로인한현금흐름",
            "영업활동으로 인한 현금흐름",
        ),
    )

    if revenue is None and operating_income is None and operating_cash_flow is None:
        return None

    return {
        "year": year,
        "revenue": revenue,
        "operating_income": operating_income,
        "operating_cash_flow": operating_cash_flow,
        "fs_div": fs_div,
    }


def _pick_amount(accounts: list[dict], names: tuple[str, ...]) -> int | None:
    normalized_names = {_normalize_account_name(name) for name in names}
    for account in accounts:
        account_name = _normalize_account_name(str(account.get("account_nm", "")))
        statement_name = str(account.get("sj_nm", ""))
        if account_name in normalized_names and "자본변동" not in statement_name:
            return _parse_amount(account.get("thstrm_amount"))
    return None


def _normalize_account_name(value: str) -> str:
    return value.replace(" ", "").replace("\u3000", "")


def _parse_amount(value) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).replace(",", "").strip()
    if text in {"-", "nan"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _fetch_market_ratios(ticker: str) -> dict:
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from pykrx import stock

    todate = datetime.today().strftime("%Y%m%d")
    fromdate = (datetime.today() - timedelta(days=14)).strftime("%Y%m%d")
    df = _call_pykrx_quietly(
        stock.get_market_fundamental_by_date,
        fromdate,
        todate,
        ticker,
    )
    if df is None or df.empty:
        return {}

    clean = df.dropna(how="all")
    if clean.empty:
        return {}

    row = clean.iloc[-1]

    def _num(col: str) -> float | None:
        value = row.get(col)
        if value is None or pd.isna(value):
            return None
        return float(value)

    return {
        "date": clean.index[-1].strftime("%Y-%m-%d"),
        "bps": _num("BPS"),
        "per": _num("PER"),
        "pbr": _num("PBR"),
        "eps": _num("EPS"),
        "div": _num("DIV"),
        "dps": _num("DPS"),
    }


def _call_pykrx_quietly(func, *args, **kwargs):
    """pykrx 일부 wrapper가 실패 시 logging 자체에서 예외를 내는 문제를 차단."""
    previous_disable_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        logging.disable(previous_disable_level)


def _build_fundamental_comment(financials: list[dict], ratios: dict) -> str:
    comments: list[str] = []

    if len(financials) >= 2:
        first = financials[0]
        last = financials[-1]
        year_count = last["year"] - first["year"] + 1
        revenue_growth = _growth_pct(first.get("revenue"), last.get("revenue"))
        op_growth = _growth_pct(
            first.get("operating_income"),
            last.get("operating_income"),
        )
        if revenue_growth is not None:
            comments.append(f"최근 {year_count}개년 매출 {revenue_growth:+.1f}%")
        if op_growth is not None:
            comments.append(f"영업이익 {op_growth:+.1f}%")

    if financials:
        latest = financials[-1]
        op_income = latest.get("operating_income")
        ocf = latest.get("operating_cash_flow")
        if op_income is not None and ocf is not None:
            if op_income > 0 and ocf > 0:
                comments.append("이익과 영업현금흐름 동반 양호")
            elif op_income > 0 and ocf <= 0:
                comments.append("이익 대비 현금흐름은 약함")
            elif op_income <= 0:
                comments.append("최근 영업이익 적자/부진")

    per = ratios.get("per")
    pbr = ratios.get("pbr")
    if per is not None and per > 0:
        if per >= 40:
            comments.append(f"PER {per:.1f}배로 고밸류")
        elif per <= 10:
            comments.append(f"PER {per:.1f}배로 저평가권")
    if pbr is not None and pbr > 0:
        comments.append(f"PBR {pbr:.2f}배")

    return " · ".join(comments[:4]) if comments else "재무 추세 확인 필요"


def _growth_pct(start: int | None, end: int | None) -> float | None:
    if start is None or end is None or start <= 0:
        return None
    return (end / start - 1) * 100
