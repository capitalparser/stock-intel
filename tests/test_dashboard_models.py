from dashboard.models import (
    CandidateStatus,
    DashboardInput,
    LensKind,
    parse_dashboard_input,
)
from dashboard.sample_data import load_sample_dashboard_input
from dashboard.market_insights import load_market_insights_dashboard_input


def test_parse_dashboard_input_accepts_same_level_lenses():
    payload = {
        "as_of": "2026-05-29",
        "price_time": "2026-05-29 00:15 UTC",
        "regime": {
            "verdict": "conditional",
            "risk_appetite": "risk-on",
            "rates": "stable",
            "dollar": "stable",
            "volatility": "low",
            "notes": ["AI infrastructure heat remains elevated"],
        },
        "market_indicators": [
            {
                "symbol": "SMH",
                "name": "Semiconductor ETF",
                "group": "반도체",
                "price": 599.83,
                "day_change_pct": 0.76,
                "read": "반도체 강세 지속",
            }
        ],
        "lenses": [
            {
                "id": "ai_agent_compute",
                "kind": "thesis",
                "name": "AI agent compute",
                "conviction": "high",
                "direction": "improving",
                "weights": {
                    "growth": 0.35,
                    "revision": 0.25,
                    "valuation": 0.15,
                    "momentum": 0.15,
                    "quality": 0.10,
                },
                "risks": ["capex fatigue"],
            },
            {
                "id": "semiconductors",
                "kind": "sector",
                "name": "Semiconductors",
                "conviction": "medium",
                "direction": "stable",
                "weights": {
                    "growth": 0.25,
                    "revision": 0.20,
                    "valuation": 0.25,
                    "momentum": 0.20,
                    "quality": 0.10,
                },
                "risks": ["valuation stretch"],
            },
        ],
        "stocks": [
            {
                "ticker": "ON",
                "company": "ON Semiconductor",
                "sector": "Power Semiconductors",
                "lens_ids": ["ai_agent_compute", "semiconductors"],
                "metrics": {
                    "valuation": 72,
                    "quality": 58,
                    "growth": 64,
                    "revision": 61,
                    "momentum": 55,
                },
                "evidence": ["AI data-center revenue doubled year over year"],
                "gaps": ["Confirm normalized PER after next earnings"],
                "thesis": "Power semi exposure can matter if AI rack power density rises.",
                "bull_case": ["Power chain demand expands beyond GPU."],
                "bear_case": ["Auto cycle drag can offset AI strength."],
                "next_action": "Check next earnings call for data-center power commentary.",
                "price": 123.77,
                "day_change_pct": 1.39,
                "pe": 91.0,
                "peer_pe": 60.0,
                "peer_group": "Power Semiconductors",
            }
        ],
    }

    parsed = parse_dashboard_input(payload)

    assert isinstance(parsed, DashboardInput)
    assert parsed.lenses[0].kind == LensKind.THESIS
    assert parsed.price_time == "2026-05-29 00:15 UTC"
    assert parsed.market_indicators[0].symbol == "SMH"
    assert parsed.lenses[1].kind == LensKind.SECTOR
    assert parsed.stocks[0].lens_ids == ["ai_agent_compute", "semiconductors"]
    assert parsed.stocks[0].thesis.startswith("Power semi exposure")
    assert parsed.stocks[0].bull_case == ["Power chain demand expands beyond GPU."]
    assert parsed.stocks[0].next_action.startswith("Check next earnings")
    assert parsed.stocks[0].price == 123.77
    assert parsed.stocks[0].pe == 91.0
    assert parsed.stocks[0].peer_pe == 60.0
    assert parsed.stocks[0].peer_group == "Power Semiconductors"
    assert CandidateStatus.WATCH.value == "Watch"


def test_parse_dashboard_input_accepts_macro_state_payload():
    payload = {
        "as_of": "2026-06-03",
        "regime": {
            "verdict": "conditional",
            "risk_appetite": "risk-on",
            "rates": "rising",
            "dollar": "stable",
            "volatility": "elevated",
            "notes": ["지수는 강하지만 유가와 금리가 경고"],
        },
        "price_time": "2026-06-03T00:00:00+00:00",
        "market_indicators": [],
        "macro_state": {
            "current_state": "fragile rally",
            "why_it_matters": "지수는 강하지만 breadth·금리·유가 중 일부가 랠리의 질을 의심하는 구간",
            "next_action": "신규 진입 강도를 낮추고 후보를 압축",
            "indicator_reads": [
                {
                    "dimension": "breadth",
                    "label": "시장 폭",
                    "state": "warning",
                    "read": "시장 폭 경고 신호",
                    "symbols": ["S5FI"],
                }
            ],
            "issues": [
                {
                    "theme": "지정학",
                    "title": "협상 신뢰도 약화",
                    "state": "unresolved",
                    "summary": "유가와 금리가 의심",
                    "triggers": ["Brent 95달러"],
                    "source_gaps": ["당사자 구속력"],
                }
            ],
            "watchlist_impact": {
                "growth_ai": "chase 제한",
                "cyclicals": "금리·유가 확인 후 압축",
                "energy_defense": "상대강도 관찰",
                "korea": "USDKRW·유가 부담 점검",
            },
            "data_gaps": [],
        },
        "lenses": [],
        "stocks": [],
    }

    parsed = parse_dashboard_input(payload)

    assert parsed.macro_state is not None
    assert parsed.macro_state.current_state == "fragile rally"
    assert parsed.macro_state.indicator_reads[0].label == "시장 폭"
    assert parsed.macro_state.issues[0].theme == "지정학"
    assert parsed.macro_state.watchlist_impact.growth_ai == "chase 제한"


def test_sample_dashboard_input_contains_initial_lens_set():
    parsed = load_sample_dashboard_input()

    lens_ids = {lens.id for lens in parsed.lenses}
    assert {
        "ai_agent_compute",
        "ai_power_bottleneck",
        "low_per_revision",
        "semiconductors",
        "power_analog",
    }.issubset(lens_ids)
    assert any(stock.ticker == "ON" for stock in parsed.stocks)
    assert any(stock.ticker == "TXN" for stock in parsed.stocks)
    assert any(stock.ticker == "VRT" for stock in parsed.stocks)
    assert any(item.symbol == "SMH" for item in parsed.market_indicators)


def test_market_insights_loader_adds_all_related_tickers(tmp_path):
    insights = tmp_path / "Market_Insights"
    (insights / "themes").mkdir(parents=True)
    (insights / "themes" / "stablecoin.md").write_text(
        "---\nlabel: \"스테이블코인 결제 레일\"\nrelated_tickers: [COIN, V, MA]\n---\n",
        encoding="utf-8",
    )

    parsed = load_market_insights_dashboard_input(insights)
    tickers = {stock.ticker for stock in parsed.stocks}

    assert {"COIN", "V", "MA"}.issubset(tickers)
    assert next(stock for stock in parsed.stocks if stock.ticker == "COIN").source_refs == [
        "스테이블코인 결제 레일"
    ]


def test_market_insights_loader_builds_filled_korean_company_card(tmp_path):
    insights = tmp_path / "Market_Insights"
    (insights / "themes").mkdir(parents=True)
    (insights / "themes" / "power.md").write_text(
        "---\n"
        "label: \"AI 전력 병목\"\n"
        "related_tickers: [034020]\n"
        "---\n",
        encoding="utf-8",
    )

    parsed = load_market_insights_dashboard_input(insights)
    stock = next(stock for stock in parsed.stocks if stock.ticker == "034020")

    assert stock.company == "두산에너빌리티"
    assert "AI 전력 병목" in stock.thesis
    assert "보강 전" not in stock.thesis
    assert any("전력" in item for item in stock.bull_case)
    assert any("가격" in item or "실적" in item for item in stock.gaps)
    assert stock.next_action.startswith("최근 가격")
