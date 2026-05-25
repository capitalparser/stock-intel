from signals.independence import decide_independence
from signals.market import Market


def test_korean_blocked_auditor_returns_confirmed_blocked_when_current_year_matches():
    audit = {
        "recent": [{"year": 2025, "firm": "삼정회계법인"}],
        "current_firm": "삼정회계법인",
    }
    decision = decide_independence(Market("KR", "한국"), audit, as_of_year=2025)
    assert decision.status == "BLOCKED_CONFIRMED"
    assert decision.auditor == "삼정회계법인"


def test_korean_clear_auditor_returns_confirmed_clear_when_current_year_matches():
    audit = {
        "recent": [{"year": 2025, "firm": "한영회계법인"}],
        "current_firm": "한영회계법인",
    }
    decision = decide_independence(Market("KR", "한국"), audit, as_of_year=2025)
    assert decision.status == "CLEAR_CONFIRMED"
    assert decision.auditor == "한영회계법인"


def test_korean_missing_auditor_returns_manual_verify():
    decision = decide_independence(Market("KR", "한국"), {"error": "no data"})
    assert decision.status == "DATA_MISSING"
    assert "감사인" in decision.reason


def test_prior_two_years_same_blocked_auditor_returns_blocked_possible():
    audit = {
        "recent": [
            {"year": 2025, "firm": "삼정회계법인"},
            {"year": 2024, "firm": "삼정회계법인"},
        ],
        "current_firm": "삼정회계법인",
    }

    decision = decide_independence(Market("KR", "한국"), audit, as_of_year=2026)

    assert decision.status == "BLOCKED_POSSIBLE"
    assert "2026 감사인 직접 확인 없음" in decision.reason


def test_prior_two_years_same_clear_auditor_returns_rollover_inferred():
    audit = {
        "recent": [
            {"year": 2025, "firm": "안진회계법인"},
            {"year": 2024, "firm": "안진회계법인"},
        ],
        "current_firm": "안진회계법인",
    }

    decision = decide_independence(Market("KR", "한국"), audit, as_of_year=2026)

    assert decision.status == "ROLLOVER_INFERRED"
    assert decision.auditor == "안진회계법인"


def test_prior_one_year_auditor_returns_manual_verify_current_year():
    audit = {
        "recent": [{"year": 2025, "firm": "한영회계법인"}],
        "current_firm": "한영회계법인",
    }

    decision = decide_independence(Market("KR", "한국"), audit, as_of_year=2026)

    assert decision.status == "MANUAL_VERIFY_CURRENT_YEAR"
    assert "2026 감사인 직접 확인 없음" in decision.reason


def test_us_returns_manual_verify_with_edgar_wording():
    decision = decide_independence(Market("US", "미국"), {})
    assert decision.status == "MANUAL_VERIFY"
    assert "EDGAR" in decision.reason


def test_japan_returns_manual_verify_with_edinet_wording():
    decision = decide_independence(Market("JP", "일본"), {})
    assert decision.status == "MANUAL_VERIFY"
    assert "EDINET" in decision.reason
