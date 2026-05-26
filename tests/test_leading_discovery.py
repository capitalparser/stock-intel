from signals.leading_discovery import (
    LeadingCandidate,
    format_leading_report,
    score_leading_candidate,
)


def test_score_leading_candidate_rewards_accumulation_before_price_reflection():
    candidate = score_leading_candidate(
        symbol="KRX:103590",
        name="일진전기",
        supply={
            "institution": {"today": 200_000_000, "5d": 1_200_000_000, "20d": 4_800_000_000},
            "foreigner": {"today": 100_000_000, "5d": 800_000_000, "20d": 2_200_000_000},
            "daily": [
                {"institution": 200_000_000, "foreigner": 100_000_000},
                {"institution": 150_000_000, "foreigner": 50_000_000},
                {"institution": 120_000_000, "foreigner": 80_000_000},
            ],
        },
        technical={
            "price": 84_000,
            "ma20": 82_000,
            "ma50": 79_000,
            "ma150": 70_000,
            "ma200": 66_000,
            "ma_trend": "정배열",
            "trend_template": "통과",
            "volume_ratio": 1.25,
            "rsi14": 58,
            "bb_pct": 66,
            "from_52w_high_pct": -12.0,
            "from_52w_low_pct": 42.0,
            "signal": "중립",
        },
        fundamental={
            "financials": [
                {"year": 2024, "revenue": 100, "operating_income": 8, "operating_cash_flow": 4},
                {"year": 2025, "revenue": 125, "operating_income": 14, "operating_cash_flow": 7},
            ],
        },
        auditor="차단 없음",
    )

    assert candidate.total_score >= 80
    assert candidate.leading_score >= 40
    assert candidate.supply_score >= 30
    assert "기관 20일 순매수" in " · ".join(candidate.evidence)
    assert "외국인 20일 순매수" in " · ".join(candidate.evidence)
    assert candidate.state == "선행 후보"


def test_score_leading_candidate_penalizes_already_reflected_or_hot_moves():
    candidate = score_leading_candidate(
        symbol="KRX:300080",
        name="플리토",
        supply={
            "institution": {"today": 0, "5d": 50_000_000, "20d": 900_000_000},
            "foreigner": {"today": 30_000_000, "5d": 400_000_000, "20d": 1_500_000_000},
            "daily": [],
        },
        technical={
            "price": 9_200,
            "ma20": 7_500,
            "ma50": 6_700,
            "ma150": 5_900,
            "ma200": 5_600,
            "ma_trend": "정배열",
            "trend_template": "통과",
            "volume_ratio": 4.2,
            "rsi14": 82,
            "bb_pct": 124,
            "from_52w_high_pct": -1.0,
            "from_52w_low_pct": 190.0,
            "signal": "매도",
        },
        fundamental={"financials": []},
        auditor="확인 필요",
    )

    assert candidate.risk_penalty >= 25
    assert candidate.total_score < 75
    assert any("이미 시세 반영" in item for item in candidate.risks)
    assert candidate.state == "대기"


def test_format_leading_report_is_telegram_card_style():
    rows = [
        LeadingCandidate(
            symbol="KRX:103590",
            name="일진전기",
            total_score=86,
            leading_score=45,
            supply_score=33,
            setup_score=24,
            fundamental_score=12,
            risk_penalty=0,
            state="선행 후보",
            evidence=["기관 20일 순매수 +48억", "외국인 20일 순매수 +22억"],
            risks=[],
            next_trigger="20일선 지지 후 Lazy Alpha 진입 라벨 확인",
            auditor="차단 없음",
        )
    ]

    text = format_leading_report(rows, scanned=12, errors=[])

    assert "🔎 국장 선행 후보" in text
    assert "1. KRX:103590 · 일진전기 · 종합 86점" in text
    assert "선행 45/50 · 수급 33/35 · 진입준비 24/30" in text
    assert "symbol |" not in text
