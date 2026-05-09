from __future__ import annotations

import contextlib
import io
from datetime import datetime, timedelta
from io import StringIO

import pandas as pd
import requests


_NAVER_SUPPLY_URL = "https://finance.naver.com/item/frgn.naver"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def _read_naver_supply_page(ticker: str, page: int) -> pd.DataFrame:
    resp = requests.get(
        _NAVER_SUPPLY_URL,
        params={"code": ticker, "page": page},
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    resp.encoding = resp.encoding or "euc-kr"

    tables = pd.read_html(StringIO(resp.text), flavor="lxml")
    for table in tables:
        if isinstance(table.columns, pd.MultiIndex):
            columns = set(table.columns)
            if (
                ("날짜", "날짜") in columns
                and ("종가", "종가") in columns
                and ("기관", "순매매량") in columns
                and ("외국인", "순매매량") in columns
            ):
                return table

    return pd.DataFrame()


def _fetch_supply_from_naver(ticker: str) -> dict:
    frames = [_read_naver_supply_page(ticker, page) for page in range(1, 5)]
    df = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
    if df.empty:
        return {"error": "수급 데이터를 가져올 수 없습니다."}

    df = df[
        [
            ("날짜", "날짜"),
            ("종가", "종가"),
            ("기관", "순매매량"),
            ("외국인", "순매매량"),
        ]
    ].copy()
    df.columns = ["date", "close", "institution_qty", "foreigner_qty"]
    df = df.dropna(subset=["date", "close", "institution_qty", "foreigner_qty"])
    if df.empty:
        return {"error": "수급 데이터를 가져올 수 없습니다."}

    df["date"] = pd.to_datetime(df["date"], format="%Y.%m.%d", errors="coerce")
    df["close"] = _to_number(df["close"])
    df["institution_qty"] = _to_number(df["institution_qty"])
    df["foreigner_qty"] = _to_number(df["foreigner_qty"])
    df = df.dropna().sort_values("date")
    if df.empty:
        return {"error": "수급 데이터를 가져올 수 없습니다."}

    # Naver exposes net buy/sell quantity, not value. Approximate amount by
    # multiplying the net quantity by that day's close so the formatter can keep
    # showing values in KRW.
    inst_value = df["institution_qty"] * df["close"]
    frgn_value = df["foreigner_qty"] * df["close"]
    daily = [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "institution": int(row.institution),
            "foreigner": int(row.foreigner),
        }
        for row in (
            pd.DataFrame(
                {
                    "date": df["date"],
                    "institution": inst_value,
                    "foreigner": frgn_value,
                }
            )
            .sort_values("date", ascending=False)
            .head(10)
            .itertuples(index=False)
        )
    ]

    return {
        "date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "institution": {
            "today": int(inst_value.iloc[-1]),
            "5d": int(inst_value.tail(5).sum()),
            "20d": int(inst_value.tail(20).sum()),
        },
        "foreigner": {
            "today": int(frgn_value.iloc[-1]),
            "5d": int(frgn_value.tail(5).sum()),
            "20d": int(frgn_value.tail(20).sum()),
        },
        "daily": daily,
    }


def fetch_supply(ticker: str) -> dict:
    """기관/외국인 순매수 현황 조회.

    Args:
        ticker: KRX 종목코드 (예: "005930")

    Returns: {
        "date": "2026-05-09",           # 기준일 (D-1 최근 거래일)
        "institution": {
            "today": 123456789,          # 오늘 순매수 (원)
            "5d": 3200000000,            # 5일 합계 순매수 (원)
            "20d": -500000000,           # 20일 합계 순매수 (원)
        },
        "foreigner": {
            "today": -89000000,
            "5d": -110000000,
            "20d": 200000000,
        },
    }
    에러 시: {"error": "수급 데이터를 가져올 수 없습니다."}
    """
    try:
        naver = _fetch_supply_from_naver(ticker)
        if "error" not in naver:
            return naver
    except Exception:
        pass

    try:
        todate = datetime.now().strftime("%Y%m%d")
        fromdate = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        with contextlib.redirect_stdout(io.StringIO()):
            from pykrx import stock

            df = stock.get_market_trading_value_by_date(
                fromdate, todate, ticker, on="순매수"
            )

        if df is None or df.empty:
            return _fetch_supply_from_naver(ticker)

        # 필수 컬럼 존재 여부 확인 (비상세 모드: 기관합계, 외국인합계)
        if "기관합계" not in df.columns or "외국인합계" not in df.columns:
            return _fetch_supply_from_naver(ticker)

        inst_col = df["기관합계"]
        frgn_col = df["외국인합계"]

        # today: 마지막 행 값
        inst_today = int(inst_col.iloc[-1])
        frgn_today = int(frgn_col.iloc[-1])

        # 5d/20d: tail(N).sum() — 마지막 행 포함
        inst_5d = int(inst_col.tail(5).sum())
        inst_20d = int(inst_col.tail(20).sum())
        frgn_5d = int(frgn_col.tail(5).sum())
        frgn_20d = int(frgn_col.tail(20).sum())
        daily = [
            {
                "date": index.strftime("%Y-%m-%d"),
                "institution": int(row["기관합계"]),
                "foreigner": int(row["외국인합계"]),
            }
            for index, row in df.sort_index(ascending=False).head(10).iterrows()
        ]

        # date: 마지막 거래일
        date_str = df.index[-1].strftime("%Y-%m-%d")

        return {
            "date": date_str,
            "institution": {
                "today": inst_today,
                "5d": inst_5d,
                "20d": inst_20d,
            },
            "foreigner": {
                "today": frgn_today,
                "5d": frgn_5d,
                "20d": frgn_20d,
            },
            "daily": daily,
        }

    except Exception:
        try:
            return _fetch_supply_from_naver(ticker)
        except Exception:
            return {"error": "수급 데이터를 가져올 수 없습니다."}
