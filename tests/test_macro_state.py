from dashboard.macro_state import build_macro_state


def test_build_macro_state_derives_fragile_rally_from_equity_strength_and_macro_warnings():
    payload = {
        "market_indicators": [
            {
                "symbol": "SPY",
                "name": "S&P 500 ETF",
                "group": "미국 대형주",
                "price": 7600.0,
                "day_change_pct": 0.7,
                "read": "미국 대형주 강세",
            },
            {
                "symbol": "RSP",
                "name": "S&P 500 동일가중",
                "group": "breadth",
                "price": 180.0,
                "day_change_pct": -0.2,
                "read": "동일가중 약세",
            },
            {
                "symbol": "S5FI",
                "name": "S&P 500 50일선 상회 비율",
                "group": "breadth",
                "price": 57.0,
                "day_change_pct": -3.0,
                "read": "breadth 약화",
            },
            {
                "symbol": "^TNX",
                "name": "미국 10년물",
                "group": "금리",
                "price": 4.52,
                "day_change_pct": 1.8,
                "read": "금리 압박",
            },
            {
                "symbol": "BZ=F",
                "name": "Brent",
                "group": "유가",
                "price": 96.0,
                "day_change_pct": 1.2,
                "read": "유가 위험",
            },
            {
                "symbol": "^VIX",
                "name": "VIX",
                "group": "심리",
                "price": 16.2,
                "day_change_pct": 4.0,
                "read": "변동성 상승",
            },
        ],
        "issues": [
            {
                "theme": "지정학",
                "title": "이란·이스라엘·레바논 협상 신뢰도 약화",
                "state": "unresolved",
                "summary": "휴전 기대는 남아 있지만 현장 충돌과 유가가 종전 신뢰도를 의심한다.",
                "triggers": ["Brent 95달러 위 고착", "10Y 4.5% 재상승", "VIX 동반 상승"],
                "source_gaps": ["헤즈볼라 묵시적 수용 여부"],
            }
        ],
    }

    state = build_macro_state(payload)

    assert state["current_state"] == "fragile rally"
    assert "지수는 강하지만" in state["why_it_matters"]
    assert state["next_action"] == "신규 진입 강도를 낮추고 후보를 압축"
    assert state["indicator_reads"][0]["dimension"] == "breadth"
    assert state["indicator_reads"][0]["state"] == "warning"
    assert state["issues"][0]["theme"] == "지정학"
    assert state["watchlist_impact"]["growth_ai"] == "chase 제한"


def test_build_macro_state_marks_missing_breadth_as_gap():
    state = build_macro_state(
        {
            "market_indicators": [
                {
                    "symbol": "SPY",
                    "name": "S&P 500 ETF",
                    "group": "미국 대형주",
                    "price": 7600.0,
                    "day_change_pct": 0.3,
                    "read": "강세",
                },
                {
                    "symbol": "^VIX",
                    "name": "VIX",
                    "group": "심리",
                    "price": 14.8,
                    "day_change_pct": -1.0,
                    "read": "변동성 진정",
                },
            ],
            "issues": [],
        }
    )

    breadth = next(item for item in state["indicator_reads"] if item["dimension"] == "breadth")
    assert breadth["state"] == "unavailable"
    assert "breadth 실데이터 미연결" in breadth["read"]
    assert "breadth 실데이터 미연결" in state["data_gaps"]
