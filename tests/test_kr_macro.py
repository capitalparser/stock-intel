import sys
from types import SimpleNamespace

from dashboard.providers.kr_macro import build_kr_indicators, realized_vol, relative_strength
from dashboard.providers.kr_macro import fetch_kr_quotes


def test_realized_vol_positive():
    closes = [100, 101, 99, 102, 98, 103] * 10
    assert realized_vol(closes) > 0


def test_relative_strength_band():
    # KOSPI가 KOSPI200보다 강하면 >50
    kospi = [100 + i * 0.4 for i in range(21)]
    kospi200 = [100 + i * 0.3 for i in range(21)]
    assert 50 < relative_strength(kospi, kospi200) <= 100


def test_relative_strength_insufficient_data_neutral():
    assert relative_strength([100, 110], [100, 105]) == 50.0


def test_build_kr_indicators_shapes_for_engine():
    fake = {
        "KOSPI": {"closes": [2500.0 + i for i in range(60)], "day_change_pct": 0.4},
        "KOSDAQ": {"closes": [130.0 + i * 0.2 for i in range(60)]},
        "USDKRW=X": {"closes": [1300.0 + i for i in range(60)], "value": 1359.0},
        "EWY": {"closes": [60.0 + i * 0.1 for i in range(60)], "value": 65.9},
    }
    inds = build_kr_indicators(quotes=fake)
    syms = {i["symbol"] for i in inds}
    assert "KOSPI" in syms and "KOSPI_BREADTH" in syms
    assert "USDKRW=X" in syms and "FOREIGN_NET" in syms
    for i in inds:
        assert "value" in i and "series" in i


def test_kospi_breadth_is_supportive_when_kosdaq_outperforms_kospi():
    fake = {
        "KOSPI": {"closes": [100.0 + i * 0.1 for i in range(60)], "day_change_pct": 0.2},
        "KOSDAQ": {"closes": [100.0 + i * 0.6 for i in range(60)], "day_change_pct": 0.8},
    }

    inds = build_kr_indicators(quotes=fake)
    breadth = next(i for i in inds if i["symbol"] == "KOSPI_BREADTH")

    assert breadth["value"] > 50.0


def test_foreign_net_is_explicit_ewy_proxy():
    fake = {"EWY": {"closes": [60.0 + i * 0.1 for i in range(60)], "value": 65.9}}
    inds = build_kr_indicators(quotes=fake)
    foreign = next(i for i in inds if i["symbol"] == "FOREIGN_NET")
    assert foreign["source_kind"] == "proxy"
    assert foreign["read"] == "EWY 프록시 — 실제 외국인 순매수 아님"


def test_fetch_kr_quotes_uses_yfinance_etf_proxies_only(monkeypatch):
    calls = []

    class FakeClose:
        def __init__(self, values):
            self._values = values

        def dropna(self):
            return self

        def tolist(self):
            return self._values

    class FakeFrame:
        def __init__(self, values):
            self._values = values

        def __getitem__(self, key):
            assert key == "Close"
            return FakeClose(self._values)

    def fake_download(symbol, *, period, interval, progress):
        calls.append((symbol, period, interval, progress))
        return FakeFrame([100.0, 101.0, 103.0])

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=fake_download))

    out = fetch_kr_quotes()

    assert [c[0] for c in calls] == ["069500.KS", "229200.KS", "USDKRW=X", "EWY"]
    assert all(c[1] == "1y" for c in calls)
    assert "^KS11" not in [c[0] for c in calls]
    assert "^KS200" not in [c[0] for c in calls]
    assert set(out) == {"KOSPI", "KOSDAQ", "USDKRW=X", "EWY"}
    assert out["KOSPI"]["closes"] == [100.0, 101.0, 103.0]
    assert out["KOSPI"]["value"] == 103.0
    assert out["KOSPI"]["day_change_pct"] > 0


def test_fetch_kr_quotes_skips_symbol_failures(monkeypatch):
    class FakeClose:
        def dropna(self):
            return self

        def tolist(self):
            return [100.0, 101.0]

    class FakeFrame:
        def __getitem__(self, key):
            return FakeClose()

    def fake_download(symbol, *, period, interval, progress):
        if symbol == "229200.KS":
            raise RuntimeError("missing")
        return FakeFrame()

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=fake_download))

    out = fetch_kr_quotes()

    assert "KOSPI" in out
    assert "KOSDAQ" not in out


def test_kr_breadth_axis_state_supportive_when_kosdaq_outperforms():
    # B-03 부호 검증을 raw value(>50)가 아니라 엔진 axis state까지 확인 (Opus review should-fix).
    # breadth state는 rs의 *자기 percentile*(ADR percentile 설계)이므로 단순 rs>50이 아니라
    # 최근 rs가 자기 범위 상단(코스닥 우위 *확대*)이어야 supportive(RISK_LOW high).
    from dashboard.macro_state import build_market_regime
    kospi = [100 + i * 0.1 for i in range(60)]          # 완만 선형
    kosdaq = [100 + 0.01 * i * i for i in range(60)]    # 가속 → rs 최근 상단
    inds = build_kr_indicators(quotes={
        "KOSPI": {"closes": kospi, "day_change_pct": 0.2, "value": kospi[-1]},
        "KOSDAQ": {"closes": kosdaq, "day_change_pct": 0.4, "value": kosdaq[-1]},
    })
    out = build_market_regime(inds, market="KR")
    breadth = next(a for a in out["axis_reads"] if a["dimension"] == "breadth")
    assert breadth["state"] == "supportive"  # 코스닥 우위 확대 → rs 고percentile → supportive
