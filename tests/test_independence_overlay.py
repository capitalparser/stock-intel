from dashboard.providers.independence_overlay import fetch_independence, independence_flag


def test_flag_mapping_blocked():
    flag, blocked = independence_flag("BLOCKED_CONFIRMED")
    assert blocked is True
    assert "독립성 차단" in flag


def test_flag_mapping_manual_verify():
    flag, blocked = independence_flag("MANUAL_VERIFY")
    assert blocked is False
    assert "독립성 확인 필요" in flag


def test_flag_mapping_clear_has_no_flag():
    flag, blocked = independence_flag("CLEAR_CONFIRMED")
    assert flag is None
    assert blocked is False


def test_fetch_independence_kr_blocked_auditor(monkeypatch):
    import dashboard.providers.independence_overlay as mod

    monkeypatch.setattr(
        mod,
        "fetch_audit_firm",
        lambda ticker: {
            "current_year": 2026,
            "current_firm": "삼정회계법인",
            "recent": [{"year": 2026, "firm": "삼정회계법인"}],
        },
    )

    out = fetch_independence("000660", as_of_year=2026)

    assert out["status"] == "BLOCKED_CONFIRMED"
    assert out["auditor"] == "삼정회계법인"


def test_fetch_independence_kr_clean_auditor(monkeypatch):
    import dashboard.providers.independence_overlay as mod

    monkeypatch.setattr(
        mod,
        "fetch_audit_firm",
        lambda ticker: {
            "current_year": 2026,
            "current_firm": "한영회계법인",
            "recent": [{"year": 2026, "firm": "한영회계법인"}],
        },
    )

    out = fetch_independence("035420", as_of_year=2026)

    assert out["status"] == "CLEAR_CONFIRMED"
    assert out["auditor"] == "한영회계법인"


def test_fetch_independence_non_kr_is_manual_verify():
    out = fetch_independence([{"ticker": "NVDA", "market": "US"}])

    assert out["NVDA"]["status"] == "MANUAL_VERIFY"
    assert out["NVDA"]["reason"] == "Market(US,미국)→MANUAL_VERIFY"


def test_fetch_independence_degrades_when_kreports_missing(monkeypatch):
    import dashboard.providers.independence_overlay as mod

    monkeypatch.setattr(
        mod,
        "fetch_audit_firm",
        lambda ticker: {"error": "kreports DB에 접근할 수 없습니다."},
    )

    out = fetch_independence("000660", as_of_year=2026)

    assert out["status"] == "DATA_MISSING"
