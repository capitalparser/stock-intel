"""Provider tests: classification, price-series math, US provider via fixtures."""

from dashboard.providers import base
from dashboard.providers.base import (
    bollinger_pct_b,
    classify_market,
    day_change_pct,
    ma_alignment,
    trailing_return_pct,
    volume_ratio,
)


def test_classify_market_kr_vs_us():
    assert classify_market("005930") == "KR"
    assert classify_market(" 000660 ") == "KR"
    assert classify_market("NVDA") == "US"
    assert classify_market("BRK.B") == "US"


def test_price_series_helpers():
    closes = [100.0] * 30 + [110.0]
    assert round(day_change_pct(closes), 2) == 10.0
    assert round(trailing_return_pct([100, 105, 110, 120], lookback=3), 6) == 20.0
    assert trailing_return_pct([100, 105], lookback=21) is None  # too short
    pct = bollinger_pct_b([10, 10, 10, 10, 10], window=5)
    assert pct == 50.0  # zero variance -> mid-band
    # average over the window includes the latest bar: avg(100,100,300)=166.7
    assert round(volume_ratio([100, 100, 300]), 1) == 1.8


def test_ma_alignment_uptrend_and_downtrend():
    up = list(range(1, 161))  # strictly increasing
    assert ma_alignment(up) == "정배열"
    down = list(range(160, 0, -1))
    assert ma_alignment(down) == "역배열"
    assert ma_alignment([1, 2, 3]) is None  # too short


def test_us_provider_maps_info_and_history(monkeypatch):
    from dashboard.providers import us

    info = {
        "trailingPE": 30.0,
        "priceToBook": 8.0,
        "operatingMargins": 0.35,
        "returnOnEquity": 0.40,
        "revenueGrowth": 0.25,
        "earningsGrowth": 0.30,
        "operatingCashflow": 1_000_000,
    }
    closes = [float(x) for x in range(100, 260)]  # 160 sessions, rising
    volumes = [1000.0] * 159 + [2000.0]

    monkeypatch.setattr(us, "_load_ticker", lambda t: (info, closes, volumes, "2026-05-30"))
    raw = us.fetch_us_stock("NVDA")

    assert raw.source == "US"
    assert raw.pe == 30.0
    assert raw.pbr == 8.0
    assert round(raw.op_margin_pct, 1) == 35.0
    assert round(raw.roe_pct, 1) == 40.0
    assert round(raw.revenue_growth_pct, 1) == 25.0
    assert raw.ocf_positive is True
    assert raw.ma_trend == "정배열"
    assert raw.price == closes[-1]
    assert raw.errors == []


def test_us_provider_degrades_on_fetch_failure(monkeypatch):
    from dashboard.providers import us

    def boom(_):
        raise RuntimeError("network down")

    monkeypatch.setattr(us, "_load_ticker", boom)
    raw = us.fetch_us_stock("NVDA")
    assert raw.price is None
    assert raw.errors and "yfinance" in raw.errors[0]


def test_dispatch_routes_to_us(monkeypatch):
    from dashboard.providers import us

    monkeypatch.setattr(us, "_load_ticker", lambda t: ({}, [1.0, 2.0], [1.0, 1.0], "2026-05-30"))
    raw = base.fetch_raw_stock("AMD")
    assert raw.source == "US"


def test_fetch_macro_includes_macro_state_from_expanded_indicators(monkeypatch):
    from dashboard.providers import macro as macro_provider

    def fake_load_quotes(symbols):
        assert "RSP" in symbols
        assert "S5FI" in symbols
        assert "BZ=F" in symbols
        return {
            "SPY": {"price": 7600.0, "day_change_pct": 0.7, "return_pct": 3.0},
            "RSP": {"price": 180.0, "day_change_pct": -0.2, "return_pct": 0.5},
            "S5FI": {"price": 57.0, "day_change_pct": -3.0, "return_pct": -4.0},
            "^VIX": {"price": 16.2, "day_change_pct": 4.0, "return_pct": 2.0},
            "^TNX": {"price": 4.52, "day_change_pct": 1.8, "return_pct": 0.2},
            "DX-Y.NYB": {"price": 97.9, "day_change_pct": 0.1, "return_pct": 0.0},
            "GLD": {"price": 310.0, "day_change_pct": 0.4, "return_pct": 1.0},
            "BZ=F": {"price": 96.0, "day_change_pct": 1.2, "return_pct": 5.0},
        }

    monkeypatch.setattr(macro_provider, "_load_quotes", fake_load_quotes)

    payload = macro_provider.fetch_macro()

    assert payload["macro_state"]["current_state"] == "fragile rally"
    assert any(item["symbol"] == "S5FI" for item in payload["market_indicators"])
    assert any(item["symbol"] == "BZ=F" for item in payload["market_indicators"])


def test_fetch_macro_indicators_carry_series(monkeypatch):
    import dashboard.providers.macro as m

    def fake_load(symbols):
        return {s: {"price": 100.0, "day_change_pct": 0.5, "return_pct": 1.0,
                    "closes": [90.0 + i for i in range(60)]} for s in symbols}

    monkeypatch.setattr(m, "_load_quotes", fake_load)
    out = m.fetch_macro()
    ind = out["market_indicators"][0]
    assert "value" in ind and "series" in ind
    assert len(ind["series"]) == 60
