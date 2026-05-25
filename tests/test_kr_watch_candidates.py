from signals.kr_watch_candidates import (
    CandidateSeed,
    evaluate_candidate,
    format_tradingview_watchlist_sections,
    group_by_sector,
    watch_status,
)


def test_watch_status_thresholds():
    assert watch_status(82, blocked=False) == "Core Watch"
    assert watch_status(70, blocked=False) == "Watch"
    assert watch_status(55, blocked=False) == "Hold for Proof"
    assert watch_status(42, blocked=False) == "Exclude"
    assert watch_status(90, blocked=True) == "Blocked Core Watch"
    assert watch_status(44, blocked=True) == "Exclude (Blocked)"


def test_evaluate_candidate_scores_fundamental_direction_and_contract_visibility():
    seed = CandidateSeed(
        symbol="KRX:103590",
        name="일진전기",
        sector="전력기기/전선/ESS/원전",
        thesis_fit=18,
        contract_visibility=18,
        notes="북미 전력기기 증설/수주잔고 후보",
    )
    fundamental = {
        "financials": [
            {"year": 2023, "revenue": 100, "operating_income": 8, "operating_cash_flow": 5},
            {"year": 2024, "revenue": 130, "operating_income": 12, "operating_cash_flow": 7},
            {"year": 2025, "revenue": 170, "operating_income": 20, "operating_cash_flow": 11},
        ]
    }
    audit = {
        "recent": [
            {"year": 2025, "firm": "삼정회계법인"},
            {"year": 2024, "firm": "삼정회계법인"},
        ],
        "current_year": 2025,
        "current_firm": "삼정회계법인",
    }

    result = evaluate_candidate(seed, fundamental=fundamental, audit=audit, as_of_year=2026)

    assert result.total_score >= 80
    assert result.status == "Blocked Core Watch"
    assert result.audit_status == "BLOCKED_POSSIBLE"


def test_format_tradingview_watchlist_sections_uses_sector_headers():
    evaluations = [
        evaluate_candidate(
            CandidateSeed("KRX:012510", "더존비즈온", "AI 소프트웨어/플랫폼", 17, 14, ""),
            fundamental={"financials": []},
            audit={},
            as_of_year=2026,
        ),
        evaluate_candidate(
            CandidateSeed("KRX:103590", "일진전기", "전력기기/전선/ESS/원전", 18, 18, ""),
            fundamental={"financials": []},
            audit={},
            as_of_year=2026,
        ),
    ]

    text = format_tradingview_watchlist_sections(evaluations, min_score=0)

    assert "###AI 소프트웨어/플랫폼" in text
    assert "KRX:012510" in text
    assert "###전력기기/전선/ESS/원전" in text
    assert group_by_sector(evaluations)["AI 소프트웨어/플랫폼"][0].symbol == "KRX:012510"
