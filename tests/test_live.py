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
    assert payload["market_indicators"][0]["symbol"] == "SPY"
    assert payload["dual_regime"]["kr"]["regime"] == "conditional"
    assert payload["as_of"] == "2026-05-30"


def test_overlay_flags_ticker_absent_from_snapshot():
    payload = _minimal_payload()
    overlay_snapshot(payload, _snapshot())
    missing = next(s for s in payload["stocks"] if s["ticker"] == "MISSING")
    assert any("실데이터 미연결" in g for g in missing["gaps"])
    # untouched quant stays curated (no price means it renders as unpriced)
    assert "price" not in missing or missing.get("price") is None


def test_overlay_sets_blocked_and_independence_evidence():
    payload = {
        "as_of": "x",
        "price_time": "x",
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
            }
        ],
    }
    snapshot = {
        "as_of": "x",
        "generated_at": "x",
        "macro": {},
        "stocks": {
            "000660": {
                "price": 210000,
                "independence_status": "BLOCKED_CONFIRMED",
                "auditor": "삼정회계법인",
                "independence_reason": "차단",
                "net_flow_signal": -1.0,
                "short_ratio": 6.2,
                "metrics": {
                    "valuation": 60,
                    "quality": 55,
                    "growth": 55,
                    "revision": 55,
                    "momentum": 55,
                },
                "data_quality": {
                    "missing": [],
                    "proxy": [],
                    "errors": [],
                    "as_of": "x",
                },
            }
        },
    }

    overlay_snapshot(payload, snapshot)

    stock = payload["stocks"][0]
    assert stock["blocked"] is True
    assert stock["independence_status"] == "BLOCKED_CONFIRMED"
    assert stock["auditor"] == "삼정회계법인"
    assert any("독립성 차단" in evidence for evidence in stock["evidence"])
    assert any("순매도" in evidence for evidence in stock["evidence"])
    assert any("공매도" in evidence for evidence in stock["evidence"])


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
