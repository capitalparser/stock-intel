from signals.backtest import PricePoint
from signals.price_history import (
    CachedPriceHistoryProvider,
    MarketPriceHistoryProvider,
    TradingViewPriceHistoryProvider,
)


class FakeTradingViewCli:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, args: list[str]) -> dict:
        self.calls.append(args)
        if args[0] == "ohlcv":
            return {
                "bars": [
                    {"time": 1_767_225_600, "close": 100.0},
                    {"time": 1_767_312_000, "close": 103.0},
                    {"time": 1_767_398_400, "close": 106.0},
                ]
            }
        return {"success": True}


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def closes(self, *, ticker: str, market: str, start: str, end: str) -> list[PricePoint]:
        self.calls += 1
        return [PricePoint(date=start, close=123.0)]


def test_tradingview_price_history_provider_reads_ohlcv_for_us_and_jp():
    runner = FakeTradingViewCli()
    provider = TradingViewPriceHistoryProvider(runner=runner, sleep_seconds=0, bars=30)

    closes = provider.closes(ticker="NASDAQ:AAPL", market="US", start="2026-01-01", end="2026-01-03")

    assert runner.calls == [
        ["symbol", "NASDAQ:AAPL"],
        ["timeframe", "D"],
        ["ohlcv", "-n", "30"],
    ]
    assert closes == [
        PricePoint(date="2026-01-01", close=100.0),
        PricePoint(date="2026-01-02", close=103.0),
        PricePoint(date="2026-01-03", close=106.0),
    ]


def test_cached_price_history_provider_reuses_same_range(tmp_path):
    inner = CountingProvider()
    provider = CachedPriceHistoryProvider(inner, db_path=tmp_path / "prices.db", ttl_seconds=3600)

    first = provider.closes(ticker="KRX:005930", market="KR", start="2026-01-01", end="2026-01-10")
    second = provider.closes(ticker="KRX:005930", market="KR", start="2026-01-01", end="2026-01-10")

    assert first == second
    assert inner.calls == 1


def test_market_price_history_provider_routes_kr_to_pykrx_and_us_jp_to_tradingview():
    kr = CountingProvider()
    tv = CountingProvider()
    provider = MarketPriceHistoryProvider(kr_provider=kr, tradingview_provider=tv)

    provider.closes(ticker="KRX:005930", market="KR", start="2026-01-01", end="2026-01-10")
    provider.closes(ticker="NASDAQ:AAPL", market="US", start="2026-01-01", end="2026-01-10")
    provider.closes(ticker="TSE:7203", market="JP", start="2026-01-01", end="2026-01-10")

    assert kr.calls == 1
    assert tv.calls == 2
