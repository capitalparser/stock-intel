import json
from pathlib import Path

from signals.filtering import FilterDecision
from signals.formatting import format_signal_alert
from signals.independence import IndependenceDecision
from signals.market import Market
from signals.payload import TradingViewSignal


FIXTURES = Path(__file__).parent / "fixtures"


def load_signal(name: str) -> TradingViewSignal:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return TradingViewSignal.model_validate(data)


def test_blocked_status_line():
    text = format_signal_alert(
        load_signal("tradingview_v6_2_buy_samsung.json"),
        Market("KR", "한국"),
        FilterDecision(True, "ALLOWED", ""),
        IndependenceDecision("BLOCKED", "차단 감사인", "삼정회계법인"),
    )
    assert text.splitlines()[0] == "🚫 독립성 차단 — 매입 검토 금지"


def test_manual_verify_status_line():
    text = format_signal_alert(
        load_signal("tradingview_v6_2_buy_aapl.json"),
        Market("US", "미국"),
        FilterDecision(True, "ALLOWED", ""),
        IndependenceDecision("MANUAL_VERIFY", "EDGAR 확인 필요", None),
    )
    assert text.splitlines()[0] == "🟡 독립성 확인 필요 — 원천 확인 전 매입 보류"


def test_clear_status_line_and_heat_warning():
    signal = load_signal("tradingview_v6_2_buy_samsung.json").model_copy(
        update={"sb_z_score": 2.8}
    )
    text = format_signal_alert(
        signal,
        Market("KR", "한국"),
        FilterDecision(True, "ALLOWED", ""),
        IndependenceDecision("CLEAR", "차단 감사인 없음", "한영회계법인"),
    )
    assert text.splitlines()[0] == "🟢 매수 시그널 — 독립성 차단 없음"
    assert "시그마 과열" in text

