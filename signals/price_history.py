"""Price history providers for signal outcome audits."""

from __future__ import annotations

from signals.backtest import PriceHistoryProvider, PricePoint
from signals.market import ticker_for_lookup


class PykrxPriceHistoryProvider(PriceHistoryProvider):
    """KR market close-price provider backed by pykrx."""

    def closes(self, *, ticker: str, market: str, start: str, end: str) -> list[PricePoint]:
        if market != "KR":
            raise ValueError(f"pykrx provider supports KR only, got {market}")

        from pykrx import stock

        lookup = ticker_for_lookup(ticker, market)
        df = stock.get_market_ohlcv_by_date(start.replace("-", ""), end.replace("-", ""), lookup)
        if df is None or df.empty:
            return []

        close_col = "종가" if "종가" in df.columns else "Close"
        return [
            PricePoint(date=index.strftime("%Y-%m-%d"), close=float(row[close_col]))
            for index, row in df.sort_index().iterrows()
        ]
