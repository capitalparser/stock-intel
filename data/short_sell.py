from __future__ import annotations

from datetime import datetime, timedelta

from pykrx import stock


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
        today = datetime.now()
        to_date = today.strftime("%Y%m%d")
        from_date = (today - timedelta(days=45)).strftime("%Y%m%d")

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
