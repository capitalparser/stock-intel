from dashboard.kr_universe import seed_to_stock
from dashboard.market_insights import build_market_insights_payload
from signals.kr_watch_candidates import CandidateSeed


def test_payload_includes_kr_screen_candidates(tmp_path):
    payload = build_market_insights_payload(insights_dir=tmp_path)
    tickers = {str(s["ticker"]) for s in payload["stocks"]}
    assert "042700" in tickers
    assert "267260" in tickers


def test_merge_kr_screen_dedups_existing_ticker():
    from dashboard.market_insights import _merge_kr_screen

    curated = [
        {
            "ticker": "000660",
            "company": "SK하이닉스",
            "sector": "기존",
            "lens_ids": ["semiconductors"],
            "source_refs": ["큐레이션"],
            "metrics": {
                "valuation": 50,
                "quality": 50,
                "growth": 50,
                "revision": 50,
                "momentum": 50,
            },
        }
    ]
    kr = [seed_to_stock(CandidateSeed("KRX:000660", "SK하이닉스", "반도체/HBM/소부장", 20, 16, "HBM"))]

    out = _merge_kr_screen(curated, kr)

    rows = [s for s in out if s["ticker"] == "000660"]
    assert len(rows) == 1
    assert "국장 스크린 (kr_watch_candidates)" in rows[0]["source_refs"]
    assert rows[0]["company"] == "SK하이닉스"


def test_existing_curated_payload_still_parses(tmp_path):
    from dashboard.models import parse_dashboard_input

    payload = build_market_insights_payload(insights_dir=tmp_path)
    parsed = parse_dashboard_input(payload)
    assert len(parsed.stocks) == len({str(s["ticker"]) for s in payload["stocks"]})


def test_kr_snapshot_overlay_replaces_neutral_seed_metrics():
    from dashboard.live import overlay_snapshot
    from dashboard.providers.base import RawStock
    from dashboard.snapshot import UniverseEntry, build_snapshot

    stock = seed_to_stock(CandidateSeed("KRX:000660", "SK하이닉스", "반도체/HBM/소부장", 20, 16, "HBM"))
    payload = {
        "as_of": "2026-06-05",
        "price_time": "seed",
        "market_indicators": [],
        "lenses": [],
        "stocks": [stock],
    }
    raw = RawStock(
        "000660",
        "KR",
        price=210000,
        day_change_pct=1.2,
        return_pct=18,
        pe=8,
        pbr=1.8,
        op_margin_pct=24,
        roe_pct=18,
        ocf_positive=True,
        revenue_growth_pct=22,
        op_growth_pct=35,
        net_flow_signal=1,
        bb_pct=78,
        ma_trend="정배열",
        volume_ratio=1.8,
        as_of="2026-06-05",
    )
    snapshot = build_snapshot(
        [UniverseEntry("000660", "반도체/HBM/소부장")],
        fetch=lambda ticker: raw,
        macro=lambda: {"market_indicators": [], "errors": []},
        as_of="2026-06-05",
    )

    overlay_snapshot(payload, snapshot)

    overlaid = payload["stocks"][0]
    assert overlaid["price"] == 210000
    assert overlaid["metrics"] != {
        "valuation": 50,
        "quality": 50,
        "growth": 50,
        "revision": 50,
        "momentum": 50,
    }
    assert any("실데이터 연결" in evidence for evidence in overlaid["evidence"])
