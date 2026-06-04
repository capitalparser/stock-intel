from dashboard.macro_state import build_market_regime
from dashboard.macro_state import build_dual_regime


def _ind(symbol, value, series, day=0.0):
    return {"symbol": symbol, "value": value, "series": series, "day_change_pct": day}


def _band(center, n=60, spread=1.0):
    return [center - spread + 2 * spread * i / (n - 1) for i in range(n)]


def test_us_fragile_rally_when_index_strong_but_breadth_warns():
    indicators = [
        _ind("SPY", 760.0, _band(720, spread=40), day=0.7),
        _ind("S5FI", 43.5, _band(60, spread=20)),     # 0.10 -> breadth warning
        _ind("^TNX", 4.40, _band(4.0, spread=0.5)),   # 0.90 -> rates warning
        _ind("^VIX", 15.0, _band(15.0, spread=2)),    # supportive
        _ind("BZ=F", 70.0, _band(70.0, spread=5)),    # supportive
    ]
    out = build_market_regime(indicators, market="US")
    assert out["market"] == "US"
    assert out["regime"] == "fragile rally"
    assert any(a["dimension"] == "breadth" and a["state"] == "warning" for a in out["axis_reads"])


def test_us_risk_on_when_all_supportive():
    indicators = [
        _ind("SPY", 760.0, _band(720, spread=40), day=0.5),
        _ind("S5FI", 70.0, _band(60, spread=20)),
        _ind("^TNX", 4.0, _band(4.0, spread=0.5)),
        _ind("^VIX", 14.0, _band(15.0, spread=2)),
        _ind("BZ=F", 68.0, _band(70.0, spread=5)),
    ]
    assert build_market_regime(indicators, market="US")["regime"] == "risk-on"


def test_all_axes_unavailable_degrades_to_conditional():
    # 대표지수만, 축 지표 없음 -> 전 축 unavailable -> conditional (risk-on 아님)
    out = build_market_regime([_ind("SPY", 760.0, _band(720, spread=40), day=0.3)], market="US")
    assert out["regime"] == "conditional"
    breadth = next(a for a in out["axis_reads"] if a["dimension"] == "breadth")
    assert breadth["state"] == "unavailable"
    assert any("breadth" in g for g in out["data_gaps"])


def test_kr_risk_off_when_fx_and_sentiment_stress():
    indicators = [
        _ind("KOSPI", 2400.0, _band(2600, spread=200), day=-1.2),
        _ind("USDKRW=X", 1500.0, _band(1350, spread=80)),  # 1.0 pctile + 1450 가드레일
        _ind("VKOSPI", 30.0, _band(20, spread=6)),         # 1.0 pctile
        _ind("KOSPI_BREADTH", 35.0, _band(55, spread=15)),
    ]
    out = build_market_regime(indicators, market="KR")
    assert out["market"] == "KR"
    assert out["regime"] == "risk-off"


def test_kr_has_no_oil_axis():
    out = build_market_regime([_ind("KOSPI", 2600.0, _band(2550, spread=80), day=0.4)], market="KR")
    assert all(a["dimension"] != "oil" for a in out["axis_reads"])


def test_build_dual_regime_attaches_transitions():
    us = [_ind("SPY", 760.0, _band(720, spread=40), day=0.5),
          _ind("S5FI", 70.0, _band(60, spread=20)),
          _ind("^VIX", 14.0, _band(15.0, spread=2))]
    kr = [_ind("KOSPI", 2600.0, _band(2550, spread=80), day=0.4),
          _ind("USDKRW=X", 1300.0, _band(1350, spread=80)),
          _ind("VKOSPI", 16.0, _band(20, spread=6))]
    history = [{"as_of": "2026-06-03",
                "us": {"market": "US", "regime": "conditional", "axis_reads": []},
                "kr": {"market": "KR", "regime": "risk-on", "axis_reads": []}}]
    out = build_dual_regime(us, kr, history=history, as_of="2026-06-04")
    assert out["as_of"] == "2026-06-04"
    assert out["us"]["regime"] == "risk-on"
    assert out["transitions"]["us"]["changed"] is True
    assert out["transitions"]["us"]["from"] == "conditional"
    assert out["transitions"]["kr"]["changed"] is False


def test_multi_symbol_axis_pctile_matches_state_symbol():
    # US breadth = RSP(supportive) + S5FI(warning). 축 state는 worst(S5FI),
    # 대표 pctile도 그 S5FI 값이어야 한다 (근거-결론 정합, code review should-fix).
    indicators = [
        _ind("SPY", 760.0, _band(720, spread=40), day=0.3),
        _ind("RSP", 210.0, _band(200, spread=20)),   # mid -> supportive, pctile ~0.5
        _ind("S5FI", 43.5, _band(60, spread=20)),    # 0.10 -> warning
    ]
    out = build_market_regime(indicators, market="US")
    breadth = next(a for a in out["axis_reads"] if a["dimension"] == "breadth")
    assert breadth["state"] == "warning"
    assert breadth["pctile"] is not None and breadth["pctile"] <= 0.15  # S5FI 값이지 RSP(0.5) 아님
