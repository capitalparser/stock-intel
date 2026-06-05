from dashboard.models import (
    CandidateStatus,
    DashboardInput,
    DualRegime,
    LensKind,
    parse_dashboard_input,
    parse_dual_regime,
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


def test_parse_stock_carries_independence():
    payload = {
        "as_of": "2026-06-05",
        "price_time": "2026-06-05T00:00:00+09:00",
        "market_indicators": [],
        "lenses": [],
        "stocks": [
            {
                "ticker": "000660",
                "company": "SK하이닉스",
                "sector": "반도체",
                "lens_ids": [],
                "metrics": {
                    "valuation": 50,
                    "quality": 50,
                    "growth": 50,
                    "revision": 50,
                    "momentum": 50,
                },
                "evidence": [],
                "gaps": [],
                "independence_status": "BLOCKED_CONFIRMED",
                "auditor": "삼정회계법인",
            }
        ],
    }

    parsed = parse_dashboard_input(payload)

    stock = parsed.stocks[0]
    assert stock.independence_status == "BLOCKED_CONFIRMED"
    assert stock.auditor == "삼정회계법인"


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


def test_parse_dual_regime():
    payload = {
        "as_of": "2026-06-04",
        "us": {"market": "US", "regime": "fragile rally", "why_it_matters": "…",
               "next_action": "후보 압축",
               "axis_reads": [{"dimension": "breadth", "label": "시장 폭",
                               "state": "warning", "pctile": 0.1, "read": "…", "symbols": ["S5FI"]}],
               "data_gaps": []},
        "kr": {"market": "KR", "regime": "risk-off", "why_it_matters": "…",
               "next_action": "방어 전환 감시", "axis_reads": [], "data_gaps": ["원화"]},
        "transitions": {
            "us": {"changed": True, "from": "risk-on", "to": "fragile rally",
                   "streak": 1, "whipsaw": True, "axis_changes": []},
            "kr": {"changed": False, "from": "risk-off", "to": "risk-off",
                   "streak": 3, "whipsaw": False, "axis_changes": []}}}
    dual = parse_dual_regime(payload)
    assert isinstance(dual, DualRegime)
    assert dual.us.regime == "fragile rally"
    assert dual.us.axis_reads[0].state == "warning"
    assert dual.transitions["us"].whipsaw is True
    assert dual.transitions["kr"].streak == 3
    assert dual.transitions["us"].from_regime == "risk-on"
    assert dual.kr.data_gaps == ["원화"]


def test_parse_dual_regime_none():
    assert parse_dual_regime(None) is None


def test_parse_dashboard_input_accepts_dual_regime_payload():
    payload = {
        "as_of": "2026-06-04",
        "price_time": "2026-06-04T00:00:00+00:00",
        "regime": {
            "verdict": "conditional",
            "risk_appetite": "neutral",
            "rates": "stable",
            "dollar": "stable",
            "volatility": "normal",
            "notes": [],
        },
        "market_indicators": [],
        "dual_regime": {
            "as_of": "2026-06-04",
            "us": {"market": "US", "regime": "risk-on", "why_it_matters": "US",
                   "next_action": "검토", "axis_reads": [], "data_gaps": []},
            "kr": {"market": "KR", "regime": "conditional", "why_it_matters": "KR",
                   "next_action": "압축",
                   "axis_reads": [{"dimension": "flow", "label": "외국인 수급",
                                   "state": "supportive", "pctile": 0.7,
                                   "read": "EWY 프록시 — 실제 외국인 순매수 아님",
                                   "symbols": ["FOREIGN_NET"], "source_kind": "proxy"}],
                   "data_gaps": []},
            "transitions": {
                "us": {"changed": False, "from": "risk-on", "to": "risk-on",
                       "streak": 2, "whipsaw": False, "axis_changes": []},
                "kr": {"changed": True, "from": "risk-off", "to": "conditional",
                       "streak": 1, "whipsaw": False, "axis_changes": []},
            },
        },
        "lenses": [],
        "stocks": [],
    }

    parsed = parse_dashboard_input(payload)

    assert parsed.dual_regime is not None
    assert parsed.dual_regime.kr.regime == "conditional"
    assert parsed.dual_regime.kr.axis_reads[0].source_kind == "proxy"


def test_parse_dashboard_input_allows_absent_legacy_regime():
    parsed = parse_dashboard_input(
        {
            "as_of": "2026-06-05",
            "price_time": "2026-06-05T00:00:00+09:00",
            "market_indicators": [],
            "dual_regime": {
                "as_of": "2026-06-05",
                "us": {"market": "US", "regime": "risk-on", "why_it_matters": "US",
                       "next_action": "검토", "axis_reads": [], "data_gaps": []},
                "kr": {"market": "KR", "regime": "conditional", "why_it_matters": "KR",
                       "next_action": "압축", "axis_reads": [], "data_gaps": []},
                "transitions": {
                    "us": {"changed": False, "from": None, "to": "risk-on",
                           "streak": 1, "whipsaw": False, "axis_changes": []},
                    "kr": {"changed": False, "from": None, "to": "conditional",
                           "streak": 1, "whipsaw": False, "axis_changes": []},
                },
            },
            "lenses": [],
            "stocks": [],
        }
    )

    assert parsed.regime is None
    assert parsed.dual_regime is not None
