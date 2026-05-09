"""기술적 지표 + 진입/매도 판단.

순수 동기 함수. pykrx OHLCV + pandas-ta 기반.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pandas_ta as ta
from pykrx import stock


# ---------------------------------------------------------------------------
# 컬럼 매핑
# ---------------------------------------------------------------------------
_KR_TO_EN = {
    "시가": "Open",
    "고가": "High",
    "저가": "Low",
    "종가": "Close",
    "거래량": "Volume",
}

# pandas-ta bbands 컬럼명 (length=20, std=2)
_BBL = "BBL_20_2.0_2.0"
_BBU = "BBU_20_2.0_2.0"


def fetch_technical(ticker: str) -> dict:
    """기술적 지표 및 진입/매도 판단 조회.

    Returns
    -------
    dict
        {
            "date": "2026-05-09",
            "price": 78400,       # 현재가 (원)
            "ma5": 77200,         # 5일 이평
            "ma20": 75800,        # 20일 이평
            "ma60": 72100,        # 60일 이평
            "rsi14": 42.3,        # RSI(14)
            "bb_pct": 52.0,       # 볼린저 %B (0~100%)
            "ma_trend": "정배열",  # 정배열 / 역배열 / 혼조
            "signal": "중립",      # 진입 / 매도 / 손절 / 중립
            "stoploss": 75000,    # 손절 기준가 (최근 20일 최저가 - 2%)
        }
    에러 시: {"error": "기술적 데이터를 가져올 수 없습니다."}
    """
    try:
        todate = datetime.today().strftime("%Y%m%d")
        fromdate = (datetime.today() - timedelta(days=120)).strftime("%Y%m%d")

        df = stock.get_market_ohlcv_by_date(fromdate, todate, ticker)
        if df is None or df.empty:
            return {"error": "기술적 데이터를 가져올 수 없습니다."}

        # 영어 컬럼으로 rename (없는 컬럼은 무시)
        df = df.rename(columns=_KR_TO_EN)

        required = {"Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(df.columns):
            return {"error": "기술적 데이터를 가져올 수 없습니다."}

        # TA 계산
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.sma(length=5, append=True)
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=60, append=True)

        row = df.iloc[-1]
        date_str = df.index[-1].strftime("%Y-%m-%d")

        def _val(col: str) -> float | None:
            """NaN → None, 나머지는 float 반환."""
            v = row.get(col)
            if v is None or pd.isna(v):
                return None
            return float(v)

        price = _val("Close")
        ma5 = _val("SMA_5")
        ma20 = _val("SMA_20")
        ma60 = _val("SMA_60")
        rsi14 = _val("RSI_14")
        bbl = _val(_BBL)
        bbu = _val(_BBU)

        # 볼린저 %B: (현재가 - 하단선) / (상단선 - 하단선) × 100
        bb_pct: float | None = None
        if price is not None and bbl is not None and bbu is not None:
            band_width = bbu - bbl
            if band_width > 0:
                bb_pct = (price - bbl) / band_width * 100

        # 이평 정배열 판단
        if ma5 is not None and ma20 is not None and ma60 is not None:
            if ma5 > ma20 > ma60:
                ma_trend = "정배열"
            elif ma5 < ma20 < ma60:
                ma_trend = "역배열"
            else:
                ma_trend = "혼조"
        else:
            ma_trend = "혼조"

        # 손절 기준가: 최근 20일 최저가 - 2%
        recent_low = df["Low"].tail(20).min()
        stoploss = int(recent_low * 0.98) if pd.notna(recent_low) else None

        # 진입/매도/손절/중립 시그널
        # 손절: 현재가 ≤ 손절 기준가
        # 진입: RSI < 35 AND 정배열
        # 매도: RSI > 70 OR 볼린저 %B > 100
        # 중립: 위 조건 미충족
        if price is not None and stoploss is not None and price <= stoploss:
            signal = "손절"
        elif rsi14 is not None and rsi14 < 35 and ma_trend == "정배열":
            signal = "진입"
        elif (rsi14 is not None and rsi14 > 70) or (bb_pct is not None and bb_pct > 100):
            signal = "매도"
        else:
            signal = "중립"

        return {
            "date": date_str,
            "price": int(price) if price is not None else None,
            "ma5": int(ma5) if ma5 is not None else None,
            "ma20": int(ma20) if ma20 is not None else None,
            "ma60": int(ma60) if ma60 is not None else None,
            "rsi14": round(rsi14, 1) if rsi14 is not None else None,
            "bb_pct": round(bb_pct, 1) if bb_pct is not None else None,
            "ma_trend": ma_trend,
            "signal": signal,
            "stoploss": stoploss,
        }

    except Exception:
        return {"error": "기술적 데이터를 가져올 수 없습니다."}
