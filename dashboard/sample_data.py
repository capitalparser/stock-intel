"""Curated v1 seed data for local dashboard rendering."""

from __future__ import annotations

from dashboard.models import DashboardInput, parse_dashboard_input


SAMPLE_DASHBOARD = {
    "as_of": "2026-05-29",
    "regime": {
        "verdict": "conditional",
        "risk_appetite": "risk-on",
        "rates": "stable",
        "dollar": "stable",
        "volatility": "low",
        "notes": [
            "AI infrastructure demand appears real, but semiconductor valuations can still correct.",
            "Power and analog semis may be a second-order AI infrastructure bottleneck.",
        ],
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
            "id": "ai_power_bottleneck",
            "kind": "thesis",
            "name": "AI power bottleneck",
            "conviction": "high",
            "direction": "improving",
            "weights": {
                "growth": 0.25,
                "revision": 0.25,
                "valuation": 0.20,
                "quality": 0.15,
                "momentum": 0.15,
            },
            "risks": ["late-cycle price hikes"],
        },
        {
            "id": "low_per_revision",
            "kind": "factor",
            "name": "Low PER + earnings revision",
            "conviction": "medium",
            "direction": "improving",
            "weights": {
                "valuation": 0.40,
                "revision": 0.30,
                "quality": 0.15,
                "growth": 0.10,
                "momentum": 0.05,
            },
            "risks": ["value trap"],
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
        {
            "id": "power_analog",
            "kind": "sector",
            "name": "Power and analog semis",
            "conviction": "medium",
            "direction": "improving",
            "weights": {
                "valuation": 0.25,
                "quality": 0.20,
                "growth": 0.20,
                "revision": 0.20,
                "momentum": 0.15,
            },
            "risks": ["auto and industrial cycle drag"],
        },
        {
            "id": "risk_on_liquidity",
            "kind": "macro",
            "name": "Risk-on liquidity",
            "conviction": "medium",
            "direction": "stable",
            "weights": {
                "momentum": 0.35,
                "growth": 0.25,
                "revision": 0.20,
                "quality": 0.10,
                "valuation": 0.10,
            },
            "risks": ["liquidity reversal"],
        },
    ],
    "stocks": [
        {
            "ticker": "ON",
            "company": "ON Semiconductor",
            "sector": "Power Semiconductors",
            "lens_ids": ["ai_power_bottleneck", "power_analog", "low_per_revision"],
            "metrics": {
                "valuation": 74,
                "quality": 58,
                "growth": 66,
                "revision": 70,
                "momentum": 60,
            },
            "evidence": ["AI data-center business reported strong growth"],
            "gaps": ["Confirm normalized earnings after next filing"],
        },
        {
            "ticker": "TXN",
            "company": "Texas Instruments",
            "sector": "Analog Semiconductors",
            "lens_ids": ["ai_power_bottleneck", "power_analog"],
            "metrics": {
                "valuation": 48,
                "quality": 78,
                "growth": 58,
                "revision": 62,
                "momentum": 68,
            },
            "evidence": ["Industrial and data-center demand commentary supports power-management exposure"],
            "gaps": [],
        },
        {
            "ticker": "ADI",
            "company": "Analog Devices",
            "sector": "Analog Semiconductors",
            "lens_ids": ["ai_power_bottleneck", "power_analog"],
            "metrics": {
                "valuation": 42,
                "quality": 82,
                "growth": 62,
                "revision": 64,
                "momentum": 70,
            },
            "evidence": ["Power-density positioning strengthened by Empower acquisition"],
            "gaps": [],
        },
        {
            "ticker": "NVDA",
            "company": "NVIDIA",
            "sector": "Accelerated Compute",
            "lens_ids": ["ai_agent_compute", "semiconductors", "risk_on_liquidity"],
            "metrics": {
                "valuation": 30,
                "quality": 92,
                "growth": 95,
                "revision": 88,
                "momentum": 90,
            },
            "evidence": ["Data-center revenue remains the primary AI infrastructure signal"],
            "gaps": ["Valuation already reflects large option value"],
        },
    ],
}


def load_sample_dashboard_input() -> DashboardInput:
    return parse_dashboard_input(SAMPLE_DASHBOARD)
