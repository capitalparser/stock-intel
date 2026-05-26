from signals.tradingview_direct import (
    classify_lazy_alpha_failure,
    classify_pre_signal_risks,
    classify_priority_risks,
    evaluate_lazy_alpha_state,
    format_tradingview_direct_report,
    is_lazy_alpha_buy_label,
    is_lazy_alpha_exit_label,
    interpret_lazy_alpha_flow,
    TradingViewLabelFlowItem,
    map_lazy_alpha_labels_to_flow,
    map_lazy_alpha_labels_to_exclusions,
    map_lazy_alpha_labels_to_outcomes,
    parse_lazy_alpha_tables,
)


def test_is_lazy_alpha_buy_label_filters_signal_texts():
    assert is_lazy_alpha_buy_label("💰 진입") is True
    assert is_lazy_alpha_buy_label("🚀채널 상방 돌파") is True
    assert is_lazy_alpha_buy_label("🔼 피라미딩 추매 1 (50%)") is True
    assert is_lazy_alpha_buy_label("💸 최종 청산") is False
    assert is_lazy_alpha_buy_label("모멘텀 SELL") is False
    assert is_lazy_alpha_buy_label("PBB") is False
    assert is_lazy_alpha_buy_label("🛠️ 셋업 형성 중") is False


def test_is_lazy_alpha_exit_label_identifies_position_reset_texts():
    assert is_lazy_alpha_exit_label("💸 최종 청산") is True
    assert is_lazy_alpha_exit_label("🛑 손절") is True
    assert is_lazy_alpha_exit_label("20일선 이탈") is True
    assert is_lazy_alpha_exit_label("모멘텀 SELL") is True
    assert is_lazy_alpha_exit_label("매도 신호") is True
    assert is_lazy_alpha_exit_label("💰 진입") is False


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


def test_map_lazy_alpha_labels_resets_entry_after_later_exit_label():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(70)
    ]
    labels = [
        {"text": "💰 진입", "x": 45, "price": None},
        {"text": "🛑 손절", "x": 48, "price": None},
    ]

    outcomes = map_lazy_alpha_labels_to_outcomes(
        symbol="NASDAQ:AAPL",
        market="US",
        bars=bars,
        labels=labels,
        total_available=70,
        duplicate_window_bars=5,
        horizons=(5,),
        active_only=True,
    )

    assert outcomes == []


def test_map_lazy_alpha_labels_resets_entry_after_later_momentum_sell_label():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(70)
    ]
    labels = [
        {"text": "💰 진입", "x": 45, "price": None},
        {"text": "모멘텀 SELL", "x": 55, "price": None},
    ]

    outcomes = map_lazy_alpha_labels_to_outcomes(
        symbol="KRX:300080",
        market="KR",
        bars=bars,
        labels=labels,
        total_available=70,
        duplicate_window_bars=5,
        horizons=(5,),
        active_only=True,
    )

    assert outcomes == []


def test_map_lazy_alpha_labels_reports_exclusion_after_later_momentum_sell_label():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(70)
    ]
    labels = [
        {"text": "💰 진입", "x": 45, "price": None},
        {"text": "모멘텀 SELL", "x": 55, "price": None},
    ]

    exclusions = map_lazy_alpha_labels_to_exclusions(
        symbol="KRX:300080",
        market="KR",
        bars=bars,
        labels=labels,
        total_available=70,
        duplicate_window_bars=5,
    )

    assert len(exclusions) == 1
    assert exclusions[0].symbol == "KRX:300080"
    assert exclusions[0].label == "💰 진입"
    assert exclusions[0].exit_label == "모멘텀 SELL"
    assert exclusions[0].score_penalty_hint == 0
    assert exclusions[0].risk_flags == []


def test_map_lazy_alpha_labels_reports_latest_exit_after_entry_for_current_state():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(300)
    ]
    labels = [
        {"text": "💰 진입", "x": 297, "price": None},
        {"text": "⚠️ 8선 이탈", "x": 300, "price": None},
        {"text": "📉 모멘텀 SELL\nENTRY: 9000\nTP: 6470\nSL: 10260\nRR: 1:2 | 5봉", "x": 409, "price": None},
    ]

    exclusions = map_lazy_alpha_labels_to_exclusions(
        symbol="KRX:300080",
        market="KR",
        bars=bars,
        labels=labels,
        duplicate_window_bars=5,
    )

    assert len(exclusions) == 1
    assert exclusions[0].exit_label.startswith("📉 모멘텀 SELL")


def test_map_lazy_alpha_labels_resets_entry_after_exit_label_beyond_loaded_bars():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(60)
    ]
    labels = [
        {"text": "💰 진입", "x": 55, "price": None},
        {"text": "📉 모멘텀 SELL", "x": 72, "price": None},
    ]

    outcomes = map_lazy_alpha_labels_to_outcomes(
        symbol="KRX:300080",
        market="KR",
        bars=bars,
        labels=labels,
        total_available=60,
        duplicate_window_bars=5,
        horizons=(5,),
        active_only=True,
    )

    assert outcomes == []


def test_map_lazy_alpha_labels_keeps_latest_entry_after_prior_exit_label():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(80)
    ]
    labels = [
        {"text": "💰 진입", "x": 40, "price": None},
        {"text": "💸 최종 청산", "x": 45, "price": None},
        {"text": "💰 진입", "x": 60, "price": None},
    ]

    outcomes = map_lazy_alpha_labels_to_outcomes(
        symbol="NASDAQ:AAPL",
        market="US",
        bars=bars,
        labels=labels,
        total_available=80,
        duplicate_window_bars=5,
        horizons=(5,),
        active_only=True,
    )

    assert len(outcomes) == 1
    assert outcomes[0].entry_price == 160


def test_map_lazy_alpha_labels_right_aligns_visible_range_label_coordinates():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(300)
    ]
    labels = [
        {"text": "🚀 돌파 진입", "x": 156, "price": None},
        {"text": "🔪 1차 분할청산", "x": 157, "price": None},
        {"text": "🔼 피라미딩 추매 1 (50%)", "x": 159, "price": None},
    ]

    outcomes = map_lazy_alpha_labels_to_outcomes(
        symbol="KRX:321370",
        market="KR",
        bars=bars,
        labels=labels,
        total_available=300,
        duplicate_window_bars=1,
        entry_policy="last",
        horizons=(5,),
        active_only=True,
    )
    exclusions = map_lazy_alpha_labels_to_exclusions(
        symbol="KRX:321370",
        market="KR",
        bars=bars,
        labels=labels,
        total_available=300,
        duplicate_window_bars=1,
        entry_policy="last",
    )

    assert len(outcomes) == 1
    assert outcomes[0].label == "🔼 피라미딩 추매 1 (50%)"
    assert outcomes[0].entry_price == 399
    assert len(exclusions) == 1
    assert exclusions[0].label == "🚀 돌파 진입"
    assert exclusions[0].exit_label == "🔪 1차 분할청산"


def test_map_lazy_alpha_labels_left_shifts_visible_range_coordinates_beyond_loaded_bars():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(300)
    ]
    labels = [
        {"text": "💰 진입", "x": 297, "price": None},
        {"text": "📉 모멘텀 SELL\nENTRY: 9000\nTP: 6470\nSL: 10260\nRR: 1:2 | 5봉", "x": 409, "price": None},
    ]

    outcomes = map_lazy_alpha_labels_to_outcomes(
        symbol="KRX:300080",
        market="KR",
        bars=bars,
        labels=labels,
        total_available=300,
        duplicate_window_bars=5,
        entry_policy="last",
        horizons=(5,),
        active_only=True,
    )
    exclusions = map_lazy_alpha_labels_to_exclusions(
        symbol="KRX:300080",
        market="KR",
        bars=bars,
        labels=labels,
        total_available=300,
        duplicate_window_bars=5,
        entry_policy="last",
    )

    assert outcomes == []
    assert len(exclusions) == 1
    assert exclusions[0].entry_bar_index == 297
    assert exclusions[0].exit_bar_index == 299
    assert exclusions[0].exit_label.startswith("📉 모멘텀 SELL")


def test_map_lazy_alpha_labels_to_flow_returns_recent_key_labels():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(300)
    ]
    labels = [
        {"text": "💰 진입", "x": 143, "price": None},
        {"text": "💸 최종 청산", "x": 144, "price": None},
        {"text": "🛠️ 셋업 형성 중", "x": 155, "price": None},
        {"text": "🚀 돌파 진입", "x": 156, "price": None},
        {"text": "🔪 1차 분할청산", "x": 157, "price": None},
        {"text": "🔼 피라미딩 추매 1 (50%)", "x": 159, "price": None},
        {"text": "PBB", "x": 159, "price": None},
    ]

    flow = map_lazy_alpha_labels_to_flow(bars=bars, labels=labels, lookback_bars=30)

    assert [item.label for item in flow] == [
        "💰 진입",
        "💸 최종 청산",
        "🛠️ 셋업 형성 중",
        "🚀 돌파 진입",
        "🔪 1차 분할청산",
        "🔼 피라미딩 추매 1 (50%)",
    ]
    assert flow[-1].bar_index == 299


def test_interpret_lazy_alpha_flow_summarizes_stage_risk_and_action():
    bars = [
        {"time": 1_700_000_000 + i * 86_400, "open": 100 + i, "high": 102 + i, "low": 98 + i, "close": 100 + i}
        for i in range(300)
    ]
    labels = [
        {"text": "💸 최종 청산", "x": 144, "price": None},
        {"text": "🛠️ 셋업 형성 중", "x": 155, "price": None},
        {"text": "🚀 돌파 진입", "x": 156, "price": None},
        {"text": "🔪 1차 분할청산", "x": 157, "price": None},
        {"text": "🔼 피라미딩 추매 1 (50%)", "x": 159, "price": None},
    ]
    flow = map_lazy_alpha_labels_to_flow(bars=bars, labels=labels, lookback_bars=30)

    interpretation = interpret_lazy_alpha_flow(flow)

    assert interpretation.stage == "재진입 후 추매 단계"
    assert interpretation.pattern == "청산 후 재진입 추매"
    assert interpretation.score_adjustment < 0
    assert interpretation.confidence == "주의"
    assert "셋업 후 돌파 진입" in interpretation.summary
    assert "청산/이탈 2회" in interpretation.risk
    assert "신규 추격보다 눌림" in interpretation.action


def test_interpret_lazy_alpha_flow_rewards_clean_setup_breakout_sequence():
    flow = [
        TradingViewLabelFlowItem("2026-05-22", "🛠️ 셋업 형성 중", 1),
        TradingViewLabelFlowItem("2026-05-25", "🚀 돌파 진입", 2),
    ]

    interpretation = interpret_lazy_alpha_flow(flow)

    assert interpretation.pattern == "셋업 후 돌파"
    assert interpretation.score_adjustment == 5
    assert interpretation.confidence == "양호"


def test_interpret_lazy_alpha_flow_penalizes_repeated_whipsaw_sequence():
    flow = [
        TradingViewLabelFlowItem("2026-05-20", "💰 진입", 1),
        TradingViewLabelFlowItem("2026-05-21", "⚠️ 8선 이탈", 2),
        TradingViewLabelFlowItem("2026-05-22", "💰 진입", 3),
        TradingViewLabelFlowItem("2026-05-23", "💣 돌파 청산", 4),
        TradingViewLabelFlowItem("2026-05-24", "🛠️ 셋업 형성 중", 5),
        TradingViewLabelFlowItem("2026-05-25", "🚀 돌파 진입", 6),
    ]

    interpretation = interpret_lazy_alpha_flow(flow)

    assert interpretation.pattern == "휩쏘 후 재돌파"
    assert interpretation.score_adjustment == -8
    assert interpretation.confidence == "위험"
    assert "청산/이탈 2회" in interpretation.risk


def test_parse_lazy_alpha_tables_extracts_score_and_risk_reward_metrics():
    payload = {
        "success": True,
        "studies": [
            {
                "name": "Lazy Alpha indicator",
                "tables": [
                    {
                        "rows": [
                            "시그널 | 🟢 포지션 보유",
                            "확신 등급 | 🟢 A (강한)",
                            "SMART 평가 | 📈 안정적 우상향\n편안한 추세 (홀딩)",
                            "EMA 정렬 | 🟢 정배열 (유지)",
                            "보조 신호 | 🟢 70점 | 돌파 W패턴 BO ",
                            "시장/섹터 | 📈 강세 정렬",
                            "추세 에너지 | 🔥 상승 가속 (23.4)",
                            "시장 주도권 | 🐂 매수세 (🔥강력)",
                            "상대 강도(RS) | 99점",
                            "거래량 강도 | 2.1배",
                            "52주 고점% | -9.1%",
                            "손절 관리(SL) | 59300 (-10.1%)",
                            "목표 수익(TP1) | 85900 (+30.1%)",
                            "실시간 손익비 | 1 : 3.1 (👍 좋음)",
                            "매수 자격 | 🟢 적합 (조건 충족)",
                            "펀더멘털 | 🌤️ 펀더멘털: 우수 (Good)",
                        ]
                    },
                    {
                        "rows": [
                            "성장 | 이번 | 직전 | 전전",
                            "EPS | 82.5% | -18.1% | -31.0%",
                            "Sales | 13.2% | 6.9% | 5.3%",
                        ]
                    },
                ],
            }
        ],
    }

    snapshot = parse_lazy_alpha_tables(payload)

    assert snapshot is not None
    assert snapshot.signal == "🟢 포지션 보유"
    assert snapshot.conviction == "🟢 A (강한)"
    assert snapshot.smart_eval == "📈 안정적 우상향 / 편안한 추세 (홀딩)"
    assert snapshot.aux_score == 70
    assert snapshot.aux_signal == "돌파 W패턴 BO"
    assert snapshot.rs_score == 99
    assert snapshot.volume_strength == 2.1
    assert snapshot.high_52w_pct == -9.1
    assert snapshot.stop_loss == 59300
    assert snapshot.stop_loss_pct == -10.1
    assert snapshot.target_price == 85900
    assert snapshot.target_return_pct == 30.1
    assert snapshot.risk_reward == "1 : 3.1 (👍 좋음)"
    assert snapshot.buy_eligibility == "🟢 적합 (조건 충족)"
    assert snapshot.eps_growth == ["82.5%", "-18.1%", "-31.0%"]
    assert snapshot.sales_growth == ["13.2%", "6.9%", "5.3%"]


def test_evaluate_lazy_alpha_state_blocks_momentum_sell_even_with_old_entry():
    decision = evaluate_lazy_alpha_state(
        outcome=None,
        exclusion_label="📉 모멘텀 SELL\nENTRY: 9000\nTP: 6470\nSL: 10260",
        table_signal="⚪️ 관망",
        table_conviction="🔴 D (역배열/꼬임)",
        table_buy_eligibility="⚠️ 미충족  진입",
        table_score=0,
        penalty=0,
    )

    assert decision.verdict == "매수 금지"
    assert "모멘텀 SELL" in decision.reason
    assert "재셋업 전까지 관망" in decision.action


def test_evaluate_lazy_alpha_state_distinguishes_exit_label_actions():
    sell = evaluate_lazy_alpha_state(exclusion_label="📉 모멘텀 SELL\nENTRY: 9000")
    final_exit = evaluate_lazy_alpha_state(exclusion_label="💸 최종 청산")
    line_break = evaluate_lazy_alpha_state(exclusion_label="⚠️ 8선 이탈")
    partial_take_profit = evaluate_lazy_alpha_state(exclusion_label="✂️ 부분 익절고려")

    assert sell.verdict == "매수 금지"
    assert "강한 매도/손절 라벨" in sell.reason
    assert "재셋업" in sell.action
    assert final_exit.verdict == "청산 완료"
    assert "포지션 초기화" in final_exit.reason
    assert "새 진입 라벨" in final_exit.action
    assert line_break.verdict == "추세 훼손"
    assert "지지선 이탈" in line_break.reason
    assert "회복" in line_break.action
    assert partial_take_profit.verdict == "보유 축소"
    assert "부분 청산" in partial_take_profit.reason
    assert "신규 진입보다" in partial_take_profit.action


def test_evaluate_lazy_alpha_state_marks_conflicting_active_signal_as_chase_risk():
    decision = evaluate_lazy_alpha_state(
        outcome_label="🚀 돌파 진입 @SR↩",
        exclusion_label=None,
        table_signal="🟢 매수 진입",
        table_conviction="🟢 A (강한)",
        table_buy_eligibility="⚠️ 미충족  진입",
        table_score=65,
        penalty=3,
    )

    assert decision.verdict == "추격 주의"
    assert "매수 자격 미충족" in decision.reason
    assert "손절선" in decision.action


def test_evaluate_lazy_alpha_state_allows_clean_initial_entry():
    decision = evaluate_lazy_alpha_state(
        outcome_label="💰 진입",
        exclusion_label=None,
        table_signal="🟢 매수 진입",
        table_conviction="🟢 A (강한)",
        table_buy_eligibility="🟢 적합 (조건 충족)",
        table_score=75,
        penalty=0,
    )

    assert decision.verdict == "진입 가능"
    assert "활성 매수 라벨" in decision.reason


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


def test_classify_priority_risks_flags_moves_already_reflected_after_entry():
    risks = classify_priority_risks(
        returns={"5d": 36.69, "10d": 64.69, "20d": 23.77},
        context={"dist_sma20_pct": 8, "dist_sma50_pct": 22},
    )

    assert "PRICE_ALREADY_MOVED_5D" in risks
    assert "PRICE_ALREADY_MOVED_10D" in risks
    assert "PRIORITY_DOWN_ALREADY_REFLECTED" in risks


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
