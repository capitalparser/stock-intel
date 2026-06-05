import json

import scripts.export_dashboard_json as exporter


TOP_LEVEL_KEYS = {
    "as_of",
    "price_time",
    "dual_regime",
    "market_indicators",
    "lenses",
    "candidates",
    "valuation_expectations",
}


def test_build_export_payload_serializes_react_contract_without_network(monkeypatch):
    monkeypatch.setattr(
        exporter,
        "build_market_insights_payload",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network fixture not injected")),
    )
    monkeypatch.setattr(
        exporter,
        "load_latest_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("snapshot fixture not injected")),
    )

    payload = exporter.build_export_payload(
        market_payload=_fake_market_payload(),
        snapshot=_fake_snapshot(),
    )

    assert set(payload) == TOP_LEVEL_KEYS
    assert payload["as_of"] == "2026-06-06"
    assert payload["price_time"] == "2026-06-06T01:02:03+00:00"
    assert payload["dual_regime"]["kr"]["regime"] == "conditional"
    assert payload["market_indicators"][0]["symbol"] == "SPY"
    assert payload["valuation_expectations"][0]["ticker"] == "AAA"

    candidate = next(item for item in payload["candidates"] if item["ticker"] == "AAA")
    assert set(candidate) == set(exporter.REQUIRED_CANDIDATE_KEYS)
    assert candidate["linked_lenses"] == [{"id": "semis", "name": "Semiconductor cycle"}]
    assert candidate["price"] == 100.0
    assert candidate["peer_pe"] == 22.0
    assert candidate["expectation_verdict"] == "정당화 가능"
    assert candidate["price_series"] == [float(i) for i in range(10, 70)]


def test_build_export_payload_defaults_missing_price_series_to_empty_list():
    payload = exporter.build_export_payload(
        market_payload=_fake_market_payload(),
        snapshot=_fake_snapshot(),
    )

    candidate = next(item for item in payload["candidates"] if item["ticker"] == "BBB")

    assert "price_series" in candidate
    assert candidate["price_series"] == []


def test_write_dashboard_json_writes_contract_file(tmp_path):
    payload = exporter.build_export_payload(
        market_payload=_fake_market_payload(),
        snapshot=_fake_snapshot(),
    )
    output_path = exporter.write_dashboard_json(payload, tmp_path / "dashboard-latest.json")

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert output_path.exists()
    assert set(written) == TOP_LEVEL_KEYS
    assert all("price_series" in candidate for candidate in written["candidates"])
    assert "valuation_expectations" in written


def _fake_market_payload():
    return {
        "as_of": "seed",
        "price_time": "seed",
        "market_indicators": [],
        "lenses": [
            {
                "id": "semis",
                "kind": "sector",
                "name": "Semiconductor cycle",
                "conviction": "high",
                "direction": "improving",
                "weights": {
                    "valuation": 0.2,
                    "quality": 0.2,
                    "growth": 0.2,
                    "revision": 0.2,
                    "momentum": 0.2,
                },
                "risks": ["cycle rollover"],
            }
        ],
        "stocks": [
            {
                "ticker": "AAA",
                "company": "Alpha Chips",
                "sector": "Semis",
                "lens_ids": ["semis"],
                "metrics": {
                    "valuation": 80,
                    "quality": 70,
                    "growth": 75,
                    "revision": 65,
                    "momentum": 72,
                },
                "evidence": ["curated evidence"],
                "gaps": [],
                "thesis": "AI memory cycle candidate.",
                "bull_case": ["cycle up"],
                "bear_case": ["cycle down"],
                "next_action": "Check next earnings.",
                "peer_group": "Semis",
            },
            {
                "ticker": "BBB",
                "company": "Beta Software",
                "sector": "Software",
                "lens_ids": [],
                "metrics": {
                    "valuation": 40,
                    "quality": 55,
                    "growth": 50,
                    "revision": 45,
                    "momentum": 42,
                },
                "evidence": ["curated evidence"],
                "gaps": ["missing price series"],
                "thesis": "Watchlist candidate.",
                "bull_case": [],
                "bear_case": [],
                "next_action": "Keep monitoring.",
                "peer_group": "Software",
            },
        ],
    }


def _fake_snapshot():
    return {
        "as_of": "2026-06-06",
        "generated_at": "2026-06-06T01:02:03+00:00",
        "macro": {
            "market_indicators": [
                {
                    "symbol": "SPY",
                    "name": "S&P 500",
                    "group": "US",
                    "price": 650.0,
                    "day_change_pct": 0.3,
                    "read": "risk-on",
                }
            ],
            "dual_regime": {
                "as_of": "2026-06-06",
                "us": {
                    "market": "US",
                    "regime": "risk-on",
                    "why_it_matters": "US liquidity supportive.",
                    "next_action": "Stay selective.",
                    "axis_reads": [],
                    "data_gaps": [],
                },
                "kr": {
                    "market": "KR",
                    "regime": "conditional",
                    "why_it_matters": "KR breadth mixed.",
                    "next_action": "Compress watchlist.",
                    "axis_reads": [],
                    "data_gaps": [],
                },
                "transitions": {
                    "us": {
                        "changed": False,
                        "from": "risk-on",
                        "to": "risk-on",
                        "streak": 3,
                        "whipsaw": False,
                        "axis_changes": [],
                    },
                    "kr": {
                        "changed": True,
                        "from": "fragile rally",
                        "to": "conditional",
                        "streak": 1,
                        "whipsaw": False,
                        "axis_changes": [],
                    },
                },
            },
        },
        "valuation_expectations": [
            {
                "ticker": "AAA",
                "forward_pe": 20.0,
                "rev_growth_pct": 18.0,
                "eps_growth_pct": 16.0,
                "fcf_margin_pct": 12.0,
                "verdict": "정당화 가능",
                "read": "growth supports multiple",
                "data_gaps": [],
            }
        ],
        "stocks": {
            "AAA": {
                "source": "US",
                "price": 100.0,
                "day_change_pct": 1.5,
                "pe": 20.0,
                "peer_pe": 22.0,
                "peer_group": "Semis",
                "metrics": {
                    "valuation": 80,
                    "quality": 70,
                    "growth": 75,
                    "revision": 65,
                    "momentum": 72,
                },
                "independence_status": "CLEAR_CONFIRMED",
                "auditor": "Clean Audit",
                "catalysts": [{"label": "earnings"}],
                "expectation_verdict": "정당화 가능",
                "closes": list(range(70)),
                "data_quality": {"missing": [], "proxy": [], "errors": [], "as_of": "2026-06-06"},
            },
            "BBB": {
                "source": "US",
                "price": 50.0,
                "day_change_pct": -0.5,
                "pe": 30.0,
                "peer_pe": 25.0,
                "peer_group": "Software",
                "metrics": {
                    "valuation": 40,
                    "quality": 55,
                    "growth": 50,
                    "revision": 45,
                    "momentum": 42,
                },
                "data_quality": {"missing": [], "proxy": [], "errors": [], "as_of": "2026-06-06"},
            },
        },
    }
