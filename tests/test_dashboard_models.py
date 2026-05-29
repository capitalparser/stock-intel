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
