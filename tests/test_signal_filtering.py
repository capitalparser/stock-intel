import json
from pathlib import Path

from signals.filtering import decide_signal_filter
from signals.payload import TradingViewSignal


FIXTURES = Path(__file__).parent / "fixtures"


def load_signal(name: str) -> TradingViewSignal:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return TradingViewSignal.model_validate(data)


def test_buy_signal_allowed_for_base_type_with_sr_suffix():
    decision = decide_signal_filter(load_signal("tradingview_v6_2_buy_aapl.json"))
    assert decision.allowed is True
    assert decision.status == "ALLOWED"


def test_sell_signal_filtered():
    decision = decide_signal_filter(load_signal("tradingview_v6_2_sell_samsung.json"))
    assert decision.allowed is False
    assert decision.status == "FILTERED"
    assert "action=SELL" in decision.reason


def test_conviction_d_filtered():
    signal = load_signal("tradingview_v6_2_buy_samsung.json").model_copy(
        update={"conviction": "D"}
    )
    decision = decide_signal_filter(signal)
    assert decision.allowed is False
    assert "conviction" in decision.reason


def test_reverse_ema_alignment_filtered():
    signal = load_signal("tradingview_v6_2_buy_samsung.json").model_copy(
        update={"ema_align": "역배열"}
    )
    decision = decide_signal_filter(signal)
    assert decision.allowed is False
    assert "ema_align" in decision.reason

