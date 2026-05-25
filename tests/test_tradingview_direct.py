from signals.tradingview_direct import (
    classify_lazy_alpha_failure,
    classify_pre_signal_risks,
    format_tradingview_direct_report,
    is_lazy_alpha_buy_label,
    map_lazy_alpha_labels_to_outcomes,
)


def test_is_lazy_alpha_buy_label_filters_signal_texts():
    assert is_lazy_alpha_buy_label("💰 진입") is True
    assert is_lazy_alpha_buy_label("🚀채널 상방 돌파") is True
    assert is_lazy_alpha_buy_label("🔼 피라미딩 추매 1 (50%)") is True
    assert is_lazy_alpha_buy_label("💸 최종 청산") is False
    assert is_lazy_alpha_buy_label("PBB") is False
    assert is_lazy_alpha_buy_label("🛠️ 셋업 형성 중") is False


def test_map_lazy_alpha_labels_to_outcomes_maps_x_to_chart_bar():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(60)
    ]
    labels = [
        {"text": "💰 진입", "x": 45, "price": None},
        {"text": "💸 최종 청산", "x": 46, "price": None},
    ]

    outcomes = map_lazy_alpha_labels_to_outcomes(
        symbol="NASDAQ:AAPL",
        market="US",
        bars=bars,
        labels=labels,
        total_available=60,
        horizons=(5, 10),
    )

    assert len(outcomes) == 1
    assert outcomes[0].entry_price == 145
    assert outcomes[0].first_signal_date == outcomes[0].signal_date
    assert outcomes[0].last_signal_date == outcomes[0].signal_date
    assert outcomes[0].duplicate_count == 1
    assert outcomes[0].risk_flags == []
    assert outcomes[0].score_penalty_hint == 0
    assert outcomes[0].returns == {"5d": 3.45, "10d": 6.9}
    assert outcomes[0].context["prior_20d_return_pct"] == 16.0


def test_map_lazy_alpha_labels_clusters_duplicate_entry_signals():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(70)
    ]
    labels = [
        {"text": "💰 진입", "x": 45, "price": None},
        {"text": "🚀채널 상방 돌파", "x": 47, "price": None},
        {"text": "🔼 피라미딩 추매 1 (50%)", "x": 50, "price": None},
    ]

    first = map_lazy_alpha_labels_to_outcomes(
        symbol="NASDAQ:AAPL",
        market="US",
        bars=bars,
        labels=labels,
        total_available=70,
        duplicate_window_bars=5,
        entry_policy="first",
        horizons=(5,),
    )
    last = map_lazy_alpha_labels_to_outcomes(
        symbol="NASDAQ:AAPL",
        market="US",
        bars=bars,
        labels=labels,
        total_available=70,
        duplicate_window_bars=5,
        entry_policy="last",
        horizons=(5,),
    )

    assert len(first) == 1
    assert first[0].entry_price == 145
    assert first[0].duplicate_count == 3
    assert "DUPLICATE_SIGNAL_CLUSTER" in first[0].risk_flags
    assert first[0].first_signal_date != first[0].last_signal_date
    assert last[0].entry_price == 150
    assert last[0].duplicate_count == 3


def test_classify_lazy_alpha_failure_separates_common_failure_modes():
    assert (
        classify_lazy_alpha_failure(
            returns={"5d": -8, "10d": -10, "20d": -12},
            context={"prior_20d_return_pct": 0},
        )
        == "외생/갭하락 의심 또는 즉시 실패"
    )


def test_classify_pre_signal_risks_flags_overheated_late_adds():
    flags = classify_pre_signal_risks(
        label="🔼 피라미딩 추매 2 (25%)",
        context={
            "prior_20d_return_pct": 65,
            "dist_sma20_pct": 30,
            "dist_sma50_pct": 45,
            "stop_distance_pct": 35,
        },
        duplicate_count=2,
    )

    assert flags == [
        "PYRAMID_ADD",
        "LATE_PYRAMID_ADD",
        "DUPLICATE_SIGNAL_CLUSTER",
        "EXTREME_20D_RUNUP",
        "SMA20_EXTENSION",
        "SMA50_EXTENSION",
        "STOP_TOO_WIDE",
    ]
    assert (
        classify_lazy_alpha_failure(
            returns={"5d": -1, "10d": -3, "20d": -8},
            context={"prior_20d_return_pct": 0},
        )
        == "페이크/휩쏘 돌파"
    )
    assert (
        classify_lazy_alpha_failure(
            returns={"5d": 4, "10d": 2, "20d": -9},
            context={"prior_20d_return_pct": 45},
        )
        == "과열 추격/확장 리스크"
    )


def test_format_report_includes_failure_class_summary():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100, "high": 102, "low": 98, "close": 100 - i}
        for i in range(70)
    ]
    outcomes = map_lazy_alpha_labels_to_outcomes(
        symbol="NYSE:AI",
        market="US",
        bars=bars,
        labels=[{"text": "💰 진입", "x": 45}],
        total_available=70,
    )

    text = format_tradingview_direct_report(outcomes, title="test")

    assert "실패 유형:" in text
    assert "사전 리스크:" in text
    assert "외생/갭하락 의심 또는 즉시 실패" in text
