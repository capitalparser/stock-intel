from dashboard.models import (
    CandidateStatus,
    DashboardInput,
    LensKind,
    parse_dashboard_input,
)


def test_parse_dashboard_input_accepts_same_level_lenses():
    payload = {
        "as_of": "2026-05-29",
        "regime": {
            "verdict": "conditional",
            "risk_appetite": "risk-on",
            "rates": "stable",
            "dollar": "stable",
            "volatility": "low",
            "notes": ["AI infrastructure heat remains elevated"],
        },
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
            }
        ],
    }

    parsed = parse_dashboard_input(payload)

    assert isinstance(parsed, DashboardInput)
    assert parsed.lenses[0].kind == LensKind.THESIS
    assert parsed.lenses[1].kind == LensKind.SECTOR
    assert parsed.stocks[0].lens_ids == ["ai_agent_compute", "semiconductors"]
    assert CandidateStatus.WATCH.value == "Watch"
