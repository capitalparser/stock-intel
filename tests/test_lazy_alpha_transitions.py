from types import SimpleNamespace

from signals.lazy_alpha_transitions import (
    LazyAlphaTransitionStore,
    SymbolLazyAlphaState,
    build_symbol_states_from_scan,
    format_transition_report,
)
from signals.tradingview_direct import (
    TradingViewExcludedSignal,
    TradingViewLabelFlowItem,
    TradingViewLabelOutcome,
    TradingViewTableSnapshot,
)


def test_transition_store_ignores_first_observation_and_reports_next_change(tmp_path):
    store = LazyAlphaTransitionStore(tmp_path / "state.db")
    setup = SymbolLazyAlphaState(
        symbol="KRX:437730",
        market="KR",
        state_key="SETUP",
        label="🛠️ 셋업 형성 중",
        label_date="2026-05-25",
        verdict="셋업 관찰",
        action="진입 라벨 대기",
    )
    entry = SymbolLazyAlphaState(
        symbol="KRX:437730",
        market="KR",
        state_key="ACTIVE_BUY",
        label="🚀 돌파 진입",
        label_date="2026-05-26",
        verdict="진입 가능",
        action="분할 진입과 무효화 라벨 확인",
    )

    assert store.record_states([setup], observed_at=100) == []
    transitions = store.record_states([entry], observed_at=200)

    assert len(transitions) == 1
    assert transitions[0].symbol == "KRX:437730"
    assert transitions[0].previous_state == "SETUP"
    assert transitions[0].current_state == "ACTIVE_BUY"
    assert transitions[0].previous_label == "🛠️ 셋업 형성 중"
    assert transitions[0].current_label == "🚀 돌파 진입"


def test_build_symbol_states_detects_setup_entry_and_exit_from_scan_result():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:437730",
        market="KR",
        signal_date="2026-05-26",
        first_signal_date="2026-05-26",
        last_signal_date="2026-05-26",
        duplicate_count=1,
        label="🚀 돌파 진입",
        entry_price=60000,
        returns={},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    exclusion = TradingViewExcludedSignal(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-21",
        label="💰 진입",
        exit_date="2026-05-26",
        exit_label="📉 모멘텀 SELL",
        entry_bar_index=10,
        exit_bar_index=20,
        risk_flags=[],
        score_penalty_hint=0,
    )
    result = SimpleNamespace(
        outcomes=[outcome],
        exclusions=[exclusion],
        scanned=["KRX:437730", "KRX:321370", "KRX:300080"],
        label_flows={
            "KRX:321370": [TradingViewLabelFlowItem("2026-05-25", "🛠️ 셋업 형성 중", 30)]
        },
        table_snapshots={},
    )

    states = {state.symbol: state for state in build_symbol_states_from_scan(result)}

    assert states["KRX:437730"].state_key == "ACTIVE_BUY"
    assert states["KRX:321370"].state_key == "SETUP"
    assert states["KRX:300080"].state_key == "EXIT"
    assert states["KRX:300080"].verdict == "매수 금지"


def test_build_symbol_states_marks_active_label_with_bearish_table_as_blocked():
    outcome = TradingViewLabelOutcome(
        symbol="KRX:300080",
        market="KR",
        signal_date="2026-05-21",
        first_signal_date="2026-05-21",
        last_signal_date="2026-05-21",
        duplicate_count=1,
        label="💰 진입",
        entry_price=10860,
        returns={},
        context={},
        risk_flags=[],
        score_penalty_hint=0,
    )
    result = SimpleNamespace(
        outcomes=[outcome],
        exclusions=[],
        scanned=["KRX:300080"],
        label_flows={},
        table_snapshots={
            "KRX:300080": TradingViewTableSnapshot(
                signal="⚪️ 관망",
                conviction="🔴 D (역배열/꼬임)",
                smart_eval="떨어지는 칼날 (접근 금지)",
                ema_alignment="🔴 약배열 (유지)",
                aux_score=1,
                aux_signal="대기",
                market_sector=None,
                trend_energy=None,
                market_control="🐻 매도세 (우위)",
                rs_score=17,
                volume_strength=1.33,
                high_52w_pct=-55.1,
                stop_loss=None,
                stop_loss_pct=None,
                target_price=None,
                target_return_pct=None,
                risk_reward=None,
                buy_eligibility="⚠️ 미충족  진입",
                fundamental=None,
                eps_growth=[],
                sales_growth=[],
                raw_rows=[],
            )
        },
    )

    states = {state.symbol: state for state in build_symbol_states_from_scan(result)}

    assert states["KRX:300080"].state_key == "BLOCKED_BUY"
    assert states["KRX:300080"].verdict == "매수 금지"
    assert states["KRX:300080"].action == "추세 회복 전까지 제외"


def test_format_transition_report_is_telegram_friendly(tmp_path):
    store = LazyAlphaTransitionStore(tmp_path / "state.db")
    store.record_states(
        [
            SymbolLazyAlphaState(
                symbol="KRX:437730",
                market="KR",
                state_key="SETUP",
                label="🛠️ 셋업 형성 중",
                label_date="2026-05-25",
                verdict="셋업 관찰",
                action="진입 라벨 대기",
            )
        ],
        observed_at=100,
    )
    transitions = store.record_states(
        [
            SymbolLazyAlphaState(
                symbol="KRX:437730",
                market="KR",
                state_key="ACTIVE_BUY",
                label="🚀 돌파 진입",
                label_date="2026-05-26",
                verdict="진입 가능",
                action="분할 진입과 무효화 라벨 확인",
            )
        ],
        observed_at=200,
    )

    text = format_transition_report(transitions, scanned_count=1, errors=[])

    assert "🔔 Lazy Alpha 상태 전환" in text
    assert "스캔: 1종목 · 전환: 1건" in text
    assert "KRX:437730" in text
    assert "SETUP → ACTIVE_BUY" in text
    assert "이전: 2026-05-25 · 🛠️ 셋업 형성 중" in text
    assert "현재: 2026-05-26 · 🚀 돌파 진입" in text
