from datetime import datetime, timedelta

from pykrx import stock


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
        todate = datetime.now().strftime("%Y%m%d")
        fromdate = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        df = stock.get_market_trading_value_by_date(
            fromdate, todate, ticker, on="순매수"
        )

        if df is None or df.empty:
            return {"error": "수급 데이터를 가져올 수 없습니다."}

        # 필수 컬럼 존재 여부 확인 (비상세 모드: 기관합계, 외국인합계)
        if "기관합계" not in df.columns or "외국인합계" not in df.columns:
            return {"error": "수급 데이터를 가져올 수 없습니다."}

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
        }

    except Exception:
        return {"error": "수급 데이터를 가져올 수 없습니다."}
