"""Live loader tests: snapshot overlay, gap flagging, sample fallback."""

from dashboard.live import (
    load_live_dashboard_input,
    overlay_snapshot,
    universe_from_payload,
)
from dashboard.market_insights import build_market_insights_payload


def _minimal_payload():
    return {
        "as_of": "2026-05-29",
        "price_time": "seed",
        "regime": {
            "verdict": "conditional", "risk_appetite": "neutral", "rates": "stable",
            "dollar": "stable", "volatility": "low", "notes": [],
        },
        "market_indicators": [],
        "lenses": [],
        "stocks": [
            {
                "ticker": "NVDA", "company": "NVIDIA", "sector": "Semis",
                "lens_ids": [], "metrics": {"valuation": 50, "quality": 50, "growth": 50,
                "revision": 50, "momentum": 50},
                "evidence": ["seed"], "gaps": ["seed gap"], "price": 1.0, "pe": 99.0,
                "peer_pe": 99.0, "peer_group": "Semis",
            },
            {
                "ticker": "MISSING", "company": "Nowhere", "sector": "Semis",
                "lens_ids": [], "metrics": {"valuation": 50, "quality": 50, "growth": 50,
                "revision": 50, "momentum": 50},
                "evidence": ["seed"], "gaps": [], "peer_group": "Semis",
            },
        ],
    }


def _snapshot():
    return {
        "as_of": "2026-05-30",
        "generated_at": "2026-05-30T00:00:00+00:00",
        "macro": {
            "market_indicators": [
                {"symbol": "SPY", "name": "S&P", "group": "대형주",
                 "price": 680.0, "day_change_pct": 0.5, "read": "ok"}
            ],
            "regime": {"verdict": "risk-on", "risk_appetite": "risk-on", "rates": "stable",
                       "dollar": "stable", "volatility": "low", "notes": ["VIX 14"]},
            "macro_state": {
                "current_state": "fragile rally",
                "why_it_matters": "fixture",
                "next_action": "후보 압축",
                "indicator_reads": [],
                "issues": [],
                "watchlist_impact": {},
                "data_gaps": [],
            },
            "dual_regime": {
                "as_of": "2026-05-30",
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
            "errors": [],
        },
        "stocks": {
            "NVDA": {
                "source": "US", "price": 950.0, "day_change_pct": 2.1, "pe": 45.0,
                "pbr": 40.0, "peer_pe": 30.0, "peer_group": "Semis",
                "metrics": {"valuation": 30, "quality": 88, "growth": 90,
                            "revision": 62, "momentum": 75},
                "data_quality": {"missing": [], "proxy": ["revision"], "errors": [],
                                 "as_of": "2026-05-30"},
            }
        },
    }


def test_overlay_replaces_quant_fields_and_macro():
    payload = _minimal_payload()
    overlay_snapshot(payload, _snapshot())

    nvda = next(s for s in payload["stocks"] if s["ticker"] == "NVDA")
    assert nvda["price"] == 950.0
    assert nvda["pe"] == 45.0
    assert nvda["peer_pe"] == 30.0
    assert nvda["metrics"]["growth"] == 90
    # real-data provenance recorded in evidence
    assert any("실데이터 연결" in e for e in nvda["evidence"])
    assert any("프록시" in e for e in nvda["evidence"])
    # curated gap preserved (no spurious data gap when nothing missing)
    assert nvda["gaps"] == ["seed gap"]

    # macro overlaid
    assert payload["regime"]["verdict"] == "risk-on"
    assert payload["market_indicators"][0]["symbol"] == "SPY"
    assert payload["macro_state"]["current_state"] == "fragile rally"
    assert payload["dual_regime"]["kr"]["regime"] == "conditional"
    assert payload["as_of"] == "2026-05-30"


def test_overlay_flags_ticker_absent_from_snapshot():
    payload = _minimal_payload()
    overlay_snapshot(payload, _snapshot())
    missing = next(s for s in payload["stocks"] if s["ticker"] == "MISSING")
    assert any("실데이터 미연결" in g for g in missing["gaps"])
    # untouched quant stays curated (no price means it renders as unpriced)
    assert "price" not in missing or missing.get("price") is None


def test_load_live_falls_back_to_sample_when_no_snapshot(tmp_path):
    # empty cache dir -> no snapshot -> curated fallback
    source_input, used_snapshot = load_live_dashboard_input(cache_dir=tmp_path)
    assert used_snapshot is False
    assert source_input.as_of == "2026-05-29"


def test_load_live_uses_injected_snapshot():
    source_input, used_snapshot = load_live_dashboard_input(snapshot=_snapshot())
    assert used_snapshot is True
    assert source_input.as_of == "2026-05-30"
    assert source_input.dual_regime is not None
    assert source_input.dual_regime.kr.regime == "conditional"


def test_universe_from_payload_uses_peer_group():
    payload = build_market_insights_payload()
    universe = universe_from_payload(payload)
    assert universe
    assert all(e.ticker for e in universe)
