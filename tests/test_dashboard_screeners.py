from dashboard.models import CandidateStatus, parse_dashboard_input
from dashboard.screeners import build_dashboard


def test_candidate_priority_comes_from_lens_overlap_and_weighted_score():
    parsed = parse_dashboard_input(
        {
            "as_of": "2026-05-29",
            "regime": {
                "verdict": "pass",
                "risk_appetite": "risk-on",
                "rates": "down",
                "dollar": "stable",
                "volatility": "low",
                "notes": [],
            },
            "lenses": [
                {
                    "id": "ai_power",
                    "kind": "thesis",
                    "name": "AI power bottleneck",
                    "conviction": "high",
                    "direction": "improving",
                    "weights": {
                        "growth": 0.30,
                        "revision": 0.25,
                        "valuation": 0.20,
                        "momentum": 0.15,
                        "quality": 0.10,
                    },
                    "risks": [],
                },
                {
                    "id": "power_semis",
                    "kind": "sector",
                    "name": "Power Semis",
                    "conviction": "medium",
                    "direction": "stable",
                    "weights": {
                        "valuation": 0.30,
                        "growth": 0.20,
                        "revision": 0.20,
                        "momentum": 0.15,
                        "quality": 0.15,
                    },
                    "risks": [],
                },
                {
                    "id": "low_per_revision",
                    "kind": "factor",
                    "name": "Low PER + revision",
                    "conviction": "medium",
                    "direction": "improving",
                    "weights": {
                        "valuation": 0.40,
                        "revision": 0.30,
                        "quality": 0.15,
                        "growth": 0.10,
                        "momentum": 0.05,
                    },
                    "risks": [],
                },
            ],
            "stocks": [
                {
                    "ticker": "ON",
                    "company": "ON Semiconductor",
                    "sector": "Power Semis",
                    "lens_ids": ["ai_power", "power_semis", "low_per_revision"],
                    "metrics": {
                        "valuation": 76,
                        "quality": 60,
                        "growth": 68,
                        "revision": 72,
                        "momentum": 61,
                    },
                    "evidence": ["AI data-center business growing"],
                    "gaps": [],
                },
                {
                    "ticker": "EXPENSIVE",
                    "company": "Expensive Compute",
                    "sector": "Semis",
                    "lens_ids": ["ai_power"],
                    "metrics": {
                        "valuation": 22,
                        "quality": 80,
                        "growth": 88,
                        "revision": 82,
                        "momentum": 85,
                    },
                    "evidence": ["Strong growth"],
                    "gaps": [],
                },
            ],
        }
    )

    dashboard = build_dashboard(parsed)

    assert dashboard.candidates[0].ticker == "ON"
    assert dashboard.candidates[0].status == CandidateStatus.SETUP
    assert dashboard.candidates[0].strongest_lens == "AI power bottleneck"
    assert dashboard.candidates[1].status == CandidateStatus.WATCH


def test_blocked_and_missing_evidence_control_status():
    parsed = parse_dashboard_input(
        {
            "as_of": "2026-05-29",
            "regime": {
                "verdict": "conditional",
                "risk_appetite": "neutral",
                "rates": "stable",
                "dollar": "stable",
                "volatility": "normal",
                "notes": [],
            },
            "lenses": [
                {
                    "id": "semis",
                    "kind": "sector",
                    "name": "Semiconductors",
                    "conviction": "medium",
                    "direction": "stable",
                    "weights": {
                        "valuation": 0.25,
                        "quality": 0.25,
                        "growth": 0.20,
                        "revision": 0.20,
                        "momentum": 0.10,
                    },
                    "risks": [],
                }
            ],
            "stocks": [
                {
                    "ticker": "KRX:005930",
                    "company": "Samsung Electronics",
                    "sector": "Semiconductors",
                    "lens_ids": ["semis"],
                    "metrics": {
                        "valuation": 70,
                        "quality": 70,
                        "growth": 55,
                        "revision": 50,
                        "momentum": 45,
                    },
                    "evidence": ["Memory cycle recovery"],
                    "gaps": [],
                    "blocked": True,
                },
                {
                    "ticker": "GAP",
                    "company": "Gap Candidate",
                    "sector": "Semiconductors",
                    "lens_ids": ["semis"],
                    "metrics": {
                        "valuation": 80,
                        "quality": 60,
                        "growth": 60,
                        "revision": 60,
                        "momentum": 60,
                    },
                    "evidence": [],
                    "gaps": ["source access gap"],
                },
            ],
        }
    )

    dashboard = build_dashboard(parsed)

    statuses = {candidate.ticker: candidate.status for candidate in dashboard.candidates}
    assert statuses["KRX:005930"] == CandidateStatus.BLOCKED
    assert statuses["GAP"] == CandidateStatus.RESEARCH


def test_build_dashboard_passes_dual_regime():
    parsed = parse_dashboard_input(
        {
            "as_of": "2026-06-04",
            "regime": {
                "verdict": "conditional",
                "risk_appetite": "neutral",
                "rates": "stable",
                "dollar": "stable",
                "volatility": "normal",
                "notes": [],
            },
            "dual_regime": {
                "as_of": "2026-06-04",
                "us": {"market": "US", "regime": "risk-on", "why_it_matters": "US",
                       "next_action": "검토", "axis_reads": [], "data_gaps": []},
                "kr": {"market": "KR", "regime": "conditional", "why_it_matters": "KR",
                       "next_action": "압축", "axis_reads": [], "data_gaps": []},
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
    )

    dashboard = build_dashboard(parsed)

    assert dashboard.dual_regime is parsed.dual_regime
