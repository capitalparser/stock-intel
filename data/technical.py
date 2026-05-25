"""기술적 지표 + 진입/매도 판단.

순수 동기 함수. pykrx OHLCV + pandas-ta 기반.
"""
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta

import pandas as pd
import pandas_ta as ta


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
            "ma50": 74500,        # 50일 이평
            "ma60": 72100,        # 60일 이평
            "ma150": 69000,       # 150일 이평
            "ma200": 65000,       # 200일 이평
            "rsi14": 42.3,        # RSI(14)
            "bb_pct": 52.0,       # 볼린저 %B (0~100%)
            "volume_ratio": 1.8,   # 거래량 / 50일 평균 거래량
            "high_52w": 85000,     # 52주 고가
            "low_52w": 51000,      # 52주 저가
            "from_52w_high_pct": -8.2,
            "from_52w_low_pct": 53.7,
            "trend_template": "통과",
            "setup_quality": "관찰",
            "technical_comment": "...",
            "ma_trend": "정배열",  # 정배열 / 역배열 / 혼조
            "signal": "중립",      # 진입 / 매도 / 손절 / 중립
            "stoploss": 75000,    # 손절 기준가 (최근 20일 최저가 - 2%)
        }
    에러 시: {"error": "기술적 데이터를 가져올 수 없습니다."}
    """
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from pykrx import stock

        todate = datetime.today().strftime("%Y%m%d")
        fromdate = (datetime.today() - timedelta(days=430)).strftime("%Y%m%d")

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
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
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=60, append=True)
        df.ta.sma(length=150, append=True)
        df.ta.sma(length=200, append=True)

        row = df.iloc[-1]
        date_str = df.index[-1].strftime("%Y-%m-%d")

        def _val(col: str) -> float | None:
            """NaN → None, 나머지는 float 반환."""
            v = row.get(col)
            if v is None or pd.isna(v):
                return None
            return float(v)

        price = _val("Close")
        volume = _val("Volume")
        ma5 = _val("SMA_5")
        ma20 = _val("SMA_20")
        ma50 = _val("SMA_50")
        ma60 = _val("SMA_60")
        ma150 = _val("SMA_150")
        ma200 = _val("SMA_200")
        rsi14 = _val("RSI_14")
        bbl = _val(_BBL)
        bbu = _val(_BBU)
        volume_ma50 = float(df["Volume"].tail(50).mean())
        high_52w = float(df["High"].tail(252).max())
        low_52w = float(df["Low"].tail(252).min())

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

        volume_ratio = None
        if volume is not None and pd.notna(volume_ma50) and volume_ma50 > 0:
            volume_ratio = volume / volume_ma50

        from_52w_high_pct = None
        from_52w_low_pct = None
        near_52w_high = False
        off_52w_low = False
        if price is not None and high_52w > 0 and low_52w > 0:
            from_52w_high_pct = (price / high_52w - 1) * 100
            from_52w_low_pct = (price / low_52w - 1) * 100
            near_52w_high = price >= high_52w * 0.75
            off_52w_low = price >= low_52w * 1.30

        trend_template_ok = False
        if (
            price is not None
            and ma50 is not None
            and ma150 is not None
            and ma200 is not None
        ):
            sma200_prev = df["SMA_200"].dropna()
            sma200_rising = len(sma200_prev) >= 22 and ma200 > float(sma200_prev.iloc[-22])
            trend_template_ok = (
                price > ma50
                and ma50 > ma150
                and ma150 > ma200
                and sma200_rising
            )

        volume_state = "평균 이하"
        if volume_ratio is not None:
            if volume_ratio >= 3.0:
                volume_state = "강한 수요"
            elif volume_ratio >= 1.5:
                volume_state = "돌파급 증가"
            elif volume_ratio >= 1.0:
                volume_state = "평균 이상"

        setup_quality = "관망"
        if trend_template_ok and near_52w_high and off_52w_low:
            if volume_ratio is not None and volume_ratio >= 1.5:
                setup_quality = "돌파 후보"
            else:
                setup_quality = "관찰"
        elif trend_template_ok:
            setup_quality = "추세 양호"
        elif price is not None and ma50 is not None and price < ma50:
            setup_quality = "리스크 관리"

        technical_comment = _build_technical_comment(
            price=price,
            ma20=ma20,
            ma50=ma50,
            ma150=ma150,
            ma200=ma200,
            trend_template_ok=trend_template_ok,
            near_52w_high=near_52w_high,
            off_52w_low=off_52w_low,
            from_52w_high_pct=from_52w_high_pct,
            from_52w_low_pct=from_52w_low_pct,
            volume_ratio=volume_ratio,
            volume_state=volume_state,
            rsi14=rsi14,
            bb_pct=bb_pct,
            setup_quality=setup_quality,
        )

        # 손절 기준가: 최근 20일 최저가 - 2%
        recent_low = df["Low"].tail(20).min()
        stoploss = int(recent_low * 0.98) if pd.notna(recent_low) else None

        # 진입/매도/손절/중립 시그널
        # 손절: 현재가 ≤ 손절 기준가
        # 진입: 성장주 트렌드 템플릿 + 52주 필터 + 돌파급 거래량
        # 매도: 단기선/핵심선 이탈, 과열권
        # 중립: 위 조건 미충족
        if price is not None and stoploss is not None and price <= stoploss:
            signal = "손절"
        elif setup_quality == "돌파 후보":
            signal = "진입"
        elif (
            price is not None
            and ((ma20 is not None and price < ma20) or (ma50 is not None and price < ma50))
        ) or (rsi14 is not None and rsi14 > 75) or (bb_pct is not None and bb_pct > 110):
            signal = "매도"
        else:
            signal = "중립"

        return {
            "date": date_str,
            "price": int(price) if price is not None else None,
            "ma5": int(ma5) if ma5 is not None else None,
            "ma20": int(ma20) if ma20 is not None else None,
            "ma50": int(ma50) if ma50 is not None else None,
            "ma60": int(ma60) if ma60 is not None else None,
            "ma150": int(ma150) if ma150 is not None else None,
            "ma200": int(ma200) if ma200 is not None else None,
            "rsi14": round(rsi14, 1) if rsi14 is not None else None,
            "bb_pct": round(bb_pct, 1) if bb_pct is not None else None,
            "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
            "volume_state": volume_state,
            "high_52w": int(high_52w) if pd.notna(high_52w) else None,
            "low_52w": int(low_52w) if pd.notna(low_52w) else None,
            "from_52w_high_pct": (
                round(from_52w_high_pct, 1) if from_52w_high_pct is not None else None
            ),
            "from_52w_low_pct": (
                round(from_52w_low_pct, 1) if from_52w_low_pct is not None else None
            ),
            "trend_template": "통과" if trend_template_ok else "미통과",
            "setup_quality": setup_quality,
            "technical_comment": technical_comment,
            "ma_trend": ma_trend,
            "signal": signal,
            "stoploss": stoploss,
        }

    except Exception:
        return {"error": "기술적 데이터를 가져올 수 없습니다."}


def _build_technical_comment(
    *,
    price: float | None,
    ma20: float | None,
    ma50: float | None,
    ma150: float | None,
    ma200: float | None,
    trend_template_ok: bool,
    near_52w_high: bool,
    off_52w_low: bool,
    from_52w_high_pct: float | None,
    from_52w_low_pct: float | None,
    volume_ratio: float | None,
    volume_state: str,
    rsi14: float | None,
    bb_pct: float | None,
    setup_quality: str,
) -> str:
    """성장주/모멘텀 관점의 모바일용 기술 코멘트."""
    comments: list[str] = []

    if trend_template_ok:
        comments.append("20/50/150/200일 구조가 성장주 추세 템플릿에 부합")
    elif price is not None and ma50 is not None and price < ma50:
        comments.append("50일선 아래라 핵심 추세 회복 확인 전까지 보수적 접근")
    elif ma50 is not None and ma150 is not None and ma200 is not None and not (ma50 > ma150 > ma200):
        comments.append("50/150/200일선 배열이 아직 정돈되지 않음")
    else:
        comments.append("장기 추세 필터 확인이 제한적")

    if near_52w_high and off_52w_low:
        if from_52w_high_pct is not None:
            comments.append(f"52주 고점 대비 {from_52w_high_pct:.1f}%로 신고가권 유지")
        else:
            comments.append("52주 고점권과 저점 대비 회복 조건 충족")
    elif not near_52w_high:
        comments.append("52주 고점과 거리가 있어 주도주 필터는 미흡")
    elif not off_52w_low and from_52w_low_pct is not None:
        comments.append(f"52주 저점 대비 +{from_52w_low_pct:.1f}%로 회복 폭 부족")

    if volume_ratio is not None:
        if volume_ratio >= 3.0:
            comments.append(f"거래량 {volume_ratio:.1f}배로 강한 피봇 수요")
        elif volume_ratio >= 1.5:
            comments.append(f"거래량 {volume_ratio:.1f}배로 돌파 확인권")
        elif volume_ratio < 1.0 and setup_quality in {"관찰", "추세 양호"}:
            comments.append("거래량은 평균 이하라 돌파 확증은 부족")
        else:
            comments.append(f"거래량은 {volume_state}")

    if price is not None and ma20 is not None and price < ma20:
        comments.append("20일선 이탈로 단기 모멘텀 둔화")
    elif price is not None and ma50 is not None and price < ma50:
        comments.append("50일선 이탈은 실패 돌파/리스크 신호")

    if rsi14 is not None and rsi14 >= 75:
        comments.append("RSI 과열권이라 추격 매수보다 눌림 확인 필요")
    elif bb_pct is not None and bb_pct > 110:
        comments.append("볼린저 상단 과확장 구간")

    return " · ".join(comments[:4])
