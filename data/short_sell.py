from __future__ import annotations

import contextlib
import io
from datetime import datetime, timedelta
from io import StringIO

import pandas as pd
import requests


_KRX_SHORT_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
_KRX_SHORT_REFERER = "https://data.krx.co.kr/comm/srt/srtLoader/index.cmd"
_NAVER_SUPPLY_URL = "https://finance.naver.com/item/frgn.naver"
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": _KRX_SHORT_REFERER,
    "X-Requested-With": "XMLHttpRequest",
}


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def _read_naver_volume_page(ticker: str, page: int) -> pd.DataFrame:
    resp = requests.get(
        _NAVER_SUPPLY_URL,
        params={"code": ticker, "page": page},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    resp.raise_for_status()
    resp.encoding = resp.encoding or "euc-kr"

    tables = pd.read_html(StringIO(resp.text), flavor="lxml")
    for table in tables:
        if isinstance(table.columns, pd.MultiIndex):
            columns = set(table.columns)
            if ("날짜", "날짜") in columns and ("거래량", "거래량") in columns:
                return table[[("날짜", "날짜"), ("거래량", "거래량")]]

    return pd.DataFrame()


def _fetch_naver_volume(ticker: str) -> pd.Series:
    frames = [_read_naver_volume_page(ticker, page) for page in range(1, 5)]
    df = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
    if df.empty:
        return pd.Series(dtype="float64")

    df.columns = ["date", "volume"]
    df = df.dropna(subset=["date", "volume"])
    df["date"] = pd.to_datetime(df["date"], format="%Y.%m.%d", errors="coerce")
    df["volume"] = _to_number(df["volume"])
    df = df.dropna()
    if df.empty:
        return pd.Series(dtype="float64")

    volume = df.drop_duplicates("date").set_index("date")["volume"].sort_index()
    return volume


def _fetch_short_sell_from_krx_out(ticker: str) -> dict:
    today = datetime.now()
    to_date = today.strftime("%Y%m%d")
    from_date = (today - timedelta(days=45)).strftime("%Y%m%d")

    with contextlib.redirect_stdout(io.StringIO()):
        from pykrx.website.krx.market.wrap import get_stock_ticker_isin

        isin = get_stock_ticker_isin(ticker)

    session = requests.Session()
    session.get(
        _KRX_SHORT_REFERER,
        params={"screenId": "MDCSTAT300", "isuCd": ticker},
        headers=_HEADERS,
        timeout=10,
    )
    resp = session.post(
        _KRX_SHORT_URL,
        data={
            "bld": "dbms/MDC_OUT/STAT/srt/MDCSTAT30001_OUT",
            "strtDd": from_date,
            "endDd": to_date,
            "isuCd": isin,
            "share": "1",
            "money": "1",
        },
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()

    df = pd.DataFrame(payload.get("OutBlock_1", []))
    if df.empty or "CVSRTSELL_TRDVOL" not in df or "TRD_DD" not in df:
        return {"error": "공매도 데이터를 가져올 수 없습니다."}

    volume = _fetch_naver_volume(ticker)
    if volume.empty:
        return {"error": "공매도 데이터를 가져올 수 없습니다."}

    short_volume = _to_number(df["CVSRTSELL_TRDVOL"])
    dates = pd.to_datetime(df["TRD_DD"], format="%Y/%m/%d")
    short_volume.index = dates

    aligned = pd.concat(
        [short_volume.rename("short_volume"), volume.rename("volume")],
        axis=1,
        join="inner",
    ).sort_index()
    ratio_series = (aligned["short_volume"] / aligned["volume"].replace(0, pd.NA)) * 100
    ratio_series = ratio_series.dropna()
    if ratio_series.empty:
        return {"error": "공매도 데이터를 가져올 수 없습니다."}

    recent_20 = ratio_series.tail(20)
    ratio_today = round(float(ratio_series.iloc[-1]), 2)
    ratio_20d_avg = round(float(recent_20.mean()), 2)

    return {
        "date": ratio_series.index[-1].strftime("%Y-%m-%d"),
        "ratio_today": ratio_today,
        "ratio_20d_avg": ratio_20d_avg,
        "trend": "▲" if ratio_today > ratio_20d_avg else "▼",
    }


def fetch_short_sell(ticker: str) -> dict:
    """공매도 비율 및 추이 조회.

    Returns: {
        "date": "2026-05-09",
        "ratio_today": 2.3,       # 오늘 공매도 비율 (%)
        "ratio_20d_avg": 1.8,     # 20일 평균 공매도 비율 (%)
        "trend": "▲",             # ▲ (오늘 > 20일평균), ▼ (오늘 < 20일평균)
    }
    에러 시: {"error": "공매도 데이터를 가져올 수 없습니다."}
    """
    try:
        krx_out = _fetch_short_sell_from_krx_out(ticker)
        if "error" not in krx_out:
            return krx_out
    except Exception:
        pass

    try:
        today = datetime.now()
        to_date = today.strftime("%Y%m%d")
        from_date = (today - timedelta(days=45)).strftime("%Y%m%d")

        with contextlib.redirect_stdout(io.StringIO()):
            from pykrx import stock

            df = stock.get_shorting_volume_by_date(from_date, to_date, ticker)

        # df는 Series(공매도/매수/비중) 또는 DataFrame — 실제 반환은 df["거래량"] 슬라이스
        # get_shorting_volume_by_date returns df["거래량"] which is a DataFrame with
        # columns: [공매도, 매수, 비중]
        if df is None or df.empty:
            return {"error": "공매도 데이터를 가져올 수 없습니다."}

        # 비중 컬럼 추출 (소수 단위 → % 환산)
        if "비중" in df.columns:
            ratio_series = df["비중"] * 100
        else:
            # 비중 컬럼이 없으면 공매도/매수로 직접 계산
            if "공매도" in df.columns and "매수" in df.columns:
                total = df["공매도"] + df["매수"]
                ratio_series = (df["공매도"] / total.replace(0, float("nan"))) * 100
            else:
                return {"error": "공매도 데이터를 가져올 수 없습니다."}

        # 거래량 0인 날(비중 0) 제외하고 최근 데이터 사용
        ratio_series = ratio_series[ratio_series > 0].dropna()

        if ratio_series.empty:
            return {"error": "공매도 데이터를 가져올 수 없습니다."}

        # 최근 20일 평균 계산
        recent_20 = ratio_series.iloc[-20:] if len(ratio_series) >= 20 else ratio_series
        ratio_today = round(float(ratio_series.iloc[-1]), 2)
        ratio_20d_avg = round(float(recent_20.mean()), 2)

        trend = "▲" if ratio_today > ratio_20d_avg else "▼"
        date_str = ratio_series.index[-1].strftime("%Y-%m-%d") if hasattr(ratio_series.index[-1], "strftime") else str(ratio_series.index[-1])[:10]

        return {
            "date": date_str,
            "ratio_today": ratio_today,
            "ratio_20d_avg": ratio_20d_avg,
            "trend": trend,
        }

    except Exception:
        return {"error": "공매도 데이터를 가져올 수 없습니다."}
