from dashboard.valuation_expectations import (
    _fcf_band,
    _growth_adjusted_multiple,
    expectation_verdict,
)


def test_growth_adjusted_multiple_uses_max_of_eps_and_half_rev():
    assert round(_growth_adjusted_multiple(36.0, 20.0, 80.0), 3) == 0.9


def test_growth_adjusted_multiple_none_when_no_growth():
    assert _growth_adjusted_multiple(36.0, 0.0, 0.0) is None
    assert _growth_adjusted_multiple(None, 20.0, 80.0) is None


def test_fcf_band():
    assert _fcf_band(40) == "strong"
    assert _fcf_band(20) == "acceptable"
    assert _fcf_band(5) == "weak"
    assert _fcf_band(None) == "unknown"


def test_verdict_data_missing_without_forward_pe():
    out = expectation_verdict(
        forward_pe=None,
        rev_growth_pct=80,
        eps_growth_pct=45,
        fcf_margin_pct=46,
    )
    assert out["verdict"] == "데이터 부족"


def test_verdict_data_missing_when_gam_is_none_after_computation():
    out = expectation_verdict(
        forward_pe=20.0,
        rev_growth_pct=0.0,
        eps_growth_pct=0.0,
        fcf_margin_pct=20.0,
    )
    assert out["verdict"] == "데이터 부족"
    assert out["reason"] == "성장률 또는 PE 없음"


def test_verdict_overheated_when_multiple_far_exceeds_growth():
    out = expectation_verdict(
        forward_pe=90.0,
        rev_growth_pct=20,
        eps_growth_pct=30,
        fcf_margin_pct=20,
    )
    assert out["verdict"] == "과열"


def test_verdict_pe_20_normal_path():
    out = expectation_verdict(
        forward_pe=20.0,
        rev_growth_pct=20.0,
        eps_growth_pct=20.0,
        fcf_margin_pct=20.0,
    )
    assert out["verdict"] == "정당화 가능"
    assert out["growth_adjusted_multiple"] == 1.0


def test_verdict_burden_band():
    out = expectation_verdict(
        forward_pe=36.0,
        rev_growth_pct=10,
        eps_growth_pct=20,
        fcf_margin_pct=46,
    )
    assert out["verdict"] == "기대치 부담"


def test_verdict_undervalued():
    out = expectation_verdict(
        forward_pe=8.0,
        rev_growth_pct=20,
        eps_growth_pct=30,
        fcf_margin_pct=35,
    )
    assert out["verdict"] == "저평가 후보"


def test_verdict_risk_when_revision_down_and_elevated_pe():
    out = expectation_verdict(
        forward_pe=45.0,
        rev_growth_pct=5,
        eps_growth_pct=5,
        fcf_margin_pct=10,
        revision_dir="down",
    )
    assert out["verdict"] == "위험"


def test_fcf_band_normal_path_surfaces_data_gaps():
    out = expectation_verdict(
        forward_pe=18.0,
        rev_growth_pct=15.0,
        eps_growth_pct=20.0,
        fcf_margin_pct=35.0,
    )
    assert out["fcf_band"] == "strong"
    assert out["data_gaps"]
    assert "v1: 성장·FCF only" in out["read"]
