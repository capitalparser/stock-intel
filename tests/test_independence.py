from signals.independence import decide_independence
from signals.market import Market


def test_korean_blocked_auditor_returns_blocked():
    audit = {
        "recent": [{"year": 2025, "firm": "삼정회계법인"}],
        "current_firm": "삼정회계법인",
    }
    decision = decide_independence(Market("KR", "한국"), audit)
    assert decision.status == "BLOCKED"
    assert decision.auditor == "삼정회계법인"


def test_korean_clear_auditor_returns_clear():
    audit = {
        "recent": [{"year": 2025, "firm": "한영회계법인"}],
        "current_firm": "한영회계법인",
    }
    decision = decide_independence(Market("KR", "한국"), audit)
    assert decision.status == "CLEAR"
    assert decision.auditor == "한영회계법인"


def test_korean_missing_auditor_returns_manual_verify():
    decision = decide_independence(Market("KR", "한국"), {"error": "no data"})
    assert decision.status == "MANUAL_VERIFY"
    assert "감사인" in decision.reason


def test_us_returns_manual_verify_with_edgar_wording():
    decision = decide_independence(Market("US", "미국"), {})
    assert decision.status == "MANUAL_VERIFY"
    assert "EDGAR" in decision.reason


def test_japan_returns_manual_verify_with_edinet_wording():
    decision = decide_independence(Market("JP", "일본"), {})
    assert decision.status == "MANUAL_VERIFY"
    assert "EDINET" in decision.reason

