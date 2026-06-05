import sys
from types import SimpleNamespace

from dashboard.providers.valuation import fetch_valuation


def _fake_yf(info):
    return SimpleNamespace(Ticker=lambda _ticker: SimpleNamespace(info=info))


def test_fetch_valuation_us_maps_fields(monkeypatch):
    info = {
        "forwardPE": 16.4,
        "revenueGrowth": 0.85,
        "earningsGrowth": 2.1,
        "freeCashflow": 46e9,
        "totalRevenue": 100e9,
        "ebitdaMargins": 0.65,
        "numberOfAnalystOpinions": 58,
        "recommendationKey": "strong_buy",
    }
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(info))

    out = fetch_valuation("NVDA")

    assert out["forward_pe"] == 16.4
    assert round(out["rev_growth_pct"], 1) == 85.0
    assert out["fcf_margin_pct"] == 46.0
    assert out["analyst_n"] == 58
    assert out["recommendation"] == "strong_buy"
    assert out["verdict"] in {"정당화 가능", "저평가 후보", "기대치 부담", "과열", "위험"}


def test_fetch_valuation_fcf_zero_is_preserved_when_revenue_positive(monkeypatch):
    info = {
        "forwardPE": 12.0,
        "revenueGrowth": 0.2,
        "earningsGrowth": 0.2,
        "freeCashflow": 0,
        "totalRevenue": 100e9,
    }
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(info))

    out = fetch_valuation("NVDA")

    assert out["forward_pe"] == 12.0
    assert out["fcf_margin_pct"] == 0.0
    assert out["fcf_band"] == "weak"


def test_fetch_valuation_zero_revenue_skips_fcf_margin(monkeypatch):
    info = {
        "forwardPE": 12.0,
        "revenueGrowth": 0.2,
        "earningsGrowth": 0.2,
        "freeCashflow": 0,
        "totalRevenue": 0,
    }
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(info))

    out = fetch_valuation("NVDA")

    assert out["fcf_margin_pct"] is None
    assert out["fcf_band"] == "unknown"


def test_fetch_valuation_negative_pe_degrades(monkeypatch):
    info = {
        "forwardPE": -3.0,
        "revenueGrowth": 0.2,
        "earningsGrowth": 0.2,
        "freeCashflow": 10,
        "totalRevenue": 100,
    }
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(info))

    out = fetch_valuation("NVDA")

    assert out["forward_pe"] is None
    assert out["verdict"] == "데이터 부족"


def test_fetch_valuation_kr_uses_ks_suffix(monkeypatch):
    captured = {}

    def Ticker(ticker):
        captured["sym"] = ticker
        return SimpleNamespace(
            info={
                "forwardPE": 5.8,
                "revenueGrowth": 0.69,
                "earningsGrowth": 4.9,
                "freeCashflow": 1e12,
                "totalRevenue": 3e12,
                "numberOfAnalystOpinions": 37,
                "recommendationKey": "buy",
            }
        )

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=Ticker))

    out = fetch_valuation("005930")

    assert captured["sym"] == "005930.KS"
    assert out["forward_pe"] == 5.8


def test_fetch_valuation_kr_falls_back_to_kq_when_ks_core_fields_empty(monkeypatch):
    captured = []

    def Ticker(ticker):
        captured.append(ticker)
        if ticker == "039030.KS":
            return SimpleNamespace(info={})
        return SimpleNamespace(
            info={
                "forwardPE": 9.5,
                "revenueGrowth": 0.15,
                "earningsGrowth": 0.2,
                "freeCashflow": 12,
                "totalRevenue": 100,
            }
        )

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=Ticker))

    out = fetch_valuation("039030")

    assert captured == ["039030.KS", "039030.KQ"]
    assert out["forward_pe"] == 9.5


def test_fetch_valuation_degrades_to_data_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf({}))

    out = fetch_valuation("NVDA")

    assert out["verdict"] == "데이터 부족"


def test_fetch_valuation_fcf_margin_independent_of_negative_pe(monkeypatch):
    # 음수 forwardPE여도 FCF 마진은 forward_pe와 무관하게 계산된다 (Opus review should-fix: 결합 분리).
    import sys
    info = {"forwardPE": -3.0, "revenueGrowth": 0.2, "earningsGrowth": -0.1,
            "freeCashflow": 30e9, "totalRevenue": 100e9}
    monkeypatch.setitem(sys.modules, "yfinance",
                        SimpleNamespace(Ticker=lambda t: SimpleNamespace(info=info)))
    out = fetch_valuation("NVDA")
    assert out["forward_pe"] is None              # 음수 PE 차단
    assert out["fcf_margin_pct"] == 30.0          # 그래도 FCF 마진은 산출(결합 분리)
