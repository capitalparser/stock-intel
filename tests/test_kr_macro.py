from dashboard.providers.kr_macro import build_kr_indicators, realized_vol, relative_strength


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
