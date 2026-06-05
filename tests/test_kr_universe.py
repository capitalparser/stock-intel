from dashboard.kr_universe import (
    KR_SECTOR_LENS,
    kr_screen_stocks,
    normalize_kr_ticker,
    seed_to_stock,
)
from signals.kr_watch_candidates import CandidateSeed


def test_normalize_strips_krx_prefix():
    assert normalize_kr_ticker("KRX:000660") == "000660"
    assert normalize_kr_ticker("000660") == "000660"


def test_seed_to_stock_shape_and_lens():
    seed = CandidateSeed("KRX:000660", "SK하이닉스", "반도체/HBM/소부장", 20, 16, "HBM/AI 메모리 대표주")
    stock = seed_to_stock(seed)
    assert stock["ticker"] == "000660"
    assert stock["company"] == "SK하이닉스"
    assert stock["sector"] == "반도체/HBM/소부장"
    assert "semiconductors" in stock["lens_ids"]
    for key in (
        "metrics",
        "thesis",
        "evidence",
        "bull_case",
        "bear_case",
        "gaps",
        "next_action",
        "source_refs",
        "peer_group",
    ):
        assert key in stock
    assert stock["metrics"] == {
        "valuation": 50,
        "quality": 50,
        "growth": 50,
        "revision": 50,
        "momentum": 50,
    }
    assert any("국장 스크린" in s for s in stock["source_refs"])
    assert "HBM/AI 메모리 대표주" in " ".join(stock["evidence"])


def test_kr_screen_stocks_covers_seeds_and_normalizes():
    stocks = kr_screen_stocks()
    tickers = {s["ticker"] for s in stocks}
    assert "000660" in tickers and "042700" in tickers
    assert all(t.isdigit() and len(t) == 6 for t in tickers)


def test_sector_lens_map_covers_all_seed_sectors():
    from signals.kr_watch_candidates import KR_CANDIDATE_SEEDS

    seed_sectors = {s.sector for s in KR_CANDIDATE_SEEDS}
    assert seed_sectors <= set(KR_SECTOR_LENS)
