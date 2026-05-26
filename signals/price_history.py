"""Price history providers for signal outcome audits."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from signals.backtest import PriceHistoryProvider, PricePoint
from signals.market import ticker_for_lookup
from signals.tradingview_scan_runner import TradingViewCli, normalize_scan_symbol


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


class TradingViewPriceHistoryProvider(PriceHistoryProvider):
    """US/JP/general close-price provider backed by the local TradingView CLI."""

    def __init__(
        self,
        *,
        mcp_dir: str | Path | None = None,
        runner: TradingViewCli | None = None,
        bars: int = 900,
        sleep_seconds: float = 1.0,
    ) -> None:
        self._runner = runner or TradingViewCli(Path(mcp_dir or "/Users/kjun/code/tradingview-mcp"))
        self._bars = bars
        self._sleep_seconds = sleep_seconds

    def closes(self, *, ticker: str, market: str, start: str, end: str) -> list[PricePoint]:
        symbol = _symbol_for_tradingview(ticker=ticker, market=market)
        self._runner.run(["symbol", symbol])
        if self._sleep_seconds:
            time.sleep(self._sleep_seconds)
        self._runner.run(["timeframe", "D"])
        if self._sleep_seconds:
            time.sleep(self._sleep_seconds)
        payload = self._runner.run(["ohlcv", "-n", str(self._bars)])
        points = [_price_point_from_bar(bar) for bar in payload.get("bars", [])]
        return [
            point
            for point in sorted((item for item in points if item is not None), key=lambda row: row.date)
            if start <= point.date <= end
        ]


class CachedPriceHistoryProvider(PriceHistoryProvider):
    """SQLite TTL cache wrapper for slow price-history providers."""

    def __init__(
        self,
        inner: PriceHistoryProvider,
        *,
        db_path: str | Path,
        ttl_seconds: int = 6 * 3600,
    ) -> None:
        self._inner = inner
        self._path = Path(db_path)
        self._ttl_seconds = ttl_seconds
        self._init()

    def closes(self, *, ticker: str, market: str, start: str, end: str) -> list[PricePoint]:
        cached = self._read(ticker=ticker, market=market, start=start, end=end)
        if cached is not None:
            return cached
        points = self._inner.closes(ticker=ticker, market=market, start=start, end=end)
        self._write(ticker=ticker, market=market, start=start, end=end, points=points)
        return points

    def _init(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history_cache (
                    ticker TEXT NOT NULL,
                    market TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    fetched_at INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (ticker, market, start_date, end_date)
                )
                """
            )
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        try:
            yield conn
        finally:
            conn.close()

    def _read(self, *, ticker: str, market: str, start: str, end: str) -> list[PricePoint] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT fetched_at, payload_json
                FROM price_history_cache
                WHERE ticker = ? AND market = ? AND start_date = ? AND end_date = ?
                """,
                (ticker, market, start, end),
            ).fetchone()
        if row is None:
            return None
        fetched_at, payload_json = row
        if int(time.time()) - int(fetched_at) > self._ttl_seconds:
            return None
        try:
            return [PricePoint(date=item["date"], close=float(item["close"])) for item in json.loads(payload_json)]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def _write(self, *, ticker: str, market: str, start: str, end: str, points: list[PricePoint]) -> None:
        payload = json.dumps([{"date": point.date, "close": point.close} for point in points])
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO price_history_cache(
                    ticker, market, start_date, end_date, fetched_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ticker, market, start, end, int(time.time()), payload),
            )
            conn.commit()


class MarketPriceHistoryProvider(PriceHistoryProvider):
    """Route KR prices to pykrx and US/JP prices to TradingView."""

    def __init__(
        self,
        *,
        kr_provider: PriceHistoryProvider | None = None,
        tradingview_provider: PriceHistoryProvider | None = None,
    ) -> None:
        self._kr_provider = kr_provider or PykrxPriceHistoryProvider()
        self._tradingview_provider = tradingview_provider or TradingViewPriceHistoryProvider()

    def closes(self, *, ticker: str, market: str, start: str, end: str) -> list[PricePoint]:
        if market == "KR":
            return self._kr_provider.closes(ticker=ticker, market=market, start=start, end=end)
        if market in {"US", "JP"}:
            return self._tradingview_provider.closes(ticker=ticker, market=market, start=start, end=end)
        raise ValueError(f"unsupported market for price history: {market}")


def _symbol_for_tradingview(*, ticker: str, market: str) -> str:
    if ":" in ticker:
        return ticker
    if market == "JP" and ticker.isdigit():
        return f"TSE:{ticker}"
    return normalize_scan_symbol(ticker)


def _price_point_from_bar(bar: dict) -> PricePoint | None:
    close = bar.get("close")
    ts = bar.get("time")
    if close is None or ts is None:
        return None
    try:
        timestamp = float(ts)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return PricePoint(
            date=datetime.fromtimestamp(timestamp).date().isoformat(),
            close=float(close),
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return None
