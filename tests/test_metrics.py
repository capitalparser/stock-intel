"""Unit tests for the metric normalization layer (no network)."""

from dashboard.metrics import (
    DEFAULT_NEUTRAL,
    build_metrics,
    growth_score,
    momentum_score,
    quality_score,
    revision_proxy_score,
    valuation_score,
)


def test_valuation_cheaper_than_peers_scores_higher():
    cheap = valuation_score(pe=10, peer_pe=20)
    rich = valuation_score(pe=40, peer_pe=20)
    assert cheap is not None and rich is not None
    assert cheap > rich
    assert 0 <= rich <= cheap <= 100


def test_valuation_missing_pe_falls_back_to_pbr_or_none():
    assert valuation_score(pe=None, peer_pe=20) is None
    assert valuation_score(pe=None, peer_pe=None, pbr=1.0) is not None
    assert valuation_score(pe=0, peer_pe=20) is None  # non-positive PE unusable


def test_scores_are_clamped_to_unit_interval():
    assert valuation_score(pe=1, peer_pe=100) <= 100
    assert valuation_score(pe=500, peer_pe=5) >= 0
    assert 0 <= momentum_score(bb_pct=0, ma_trend="역배열", return_pct=-50) <= 100
    assert 0 <= momentum_score(bb_pct=100, ma_trend="정배열", return_pct=80) <= 100


def test_quality_monotonic_in_margin():
    low = quality_score(op_margin_pct=2)
    high = quality_score(op_margin_pct=35)
    assert low < high
    # OCF confirmation nudges score
    assert quality_score(op_margin_pct=20, ocf_positive=True) > quality_score(
        op_margin_pct=20, ocf_positive=False
    )


def test_growth_blends_revenue_and_operating_income():
    assert growth_score(None, None) is None
    fast = growth_score(revenue_growth_pct=50, op_growth_pct=50)
    slow = growth_score(revenue_growth_pct=0, op_growth_pct=0)
    assert fast > slow


def test_revision_proxy_reacts_to_flow_and_trend():
    buy = revision_proxy_score(net_flow_signal=1.0, trend_signal="정배열")
    sell = revision_proxy_score(net_flow_signal=-1.0, trend_signal="역배열")
    assert buy > 50 > sell
    assert revision_proxy_score(None, None) is None


def test_build_metrics_marks_missing_and_proxy():
    result = build_metrics(
        pe=None, peer_pe=None, pbr=None,
        op_margin_pct=None, ocf_positive=None, roe_pct=None,
        revenue_growth_pct=None, op_growth_pct=None,
        net_flow_signal=None, ma_trend=None, bb_pct=None,
        return_pct=None, volume_ratio=None,
    )
    # Everything missing -> all five neutral and flagged missing.
    assert set(result.scores) == {"valuation", "quality", "growth", "revision", "momentum"}
    assert all(v == DEFAULT_NEUTRAL for v in result.scores.values())
    assert set(result.missing) == {"valuation", "quality", "growth", "revision", "momentum"}
    assert result.proxy == []  # revision missing -> not counted as proxy


def test_build_metrics_full_inputs_have_no_missing_and_revision_proxy():
    result = build_metrics(
        pe=15, peer_pe=20, pbr=2.0,
        op_margin_pct=25, ocf_positive=True, roe_pct=18,
        revenue_growth_pct=20, op_growth_pct=25,
        net_flow_signal=1.0, ma_trend="정배열", bb_pct=60,
        return_pct=10, volume_ratio=1.4,
    )
    assert result.missing == []
    assert result.proxy == ["revision"]
    assert all(0 <= v <= 100 for v in result.scores.values())
