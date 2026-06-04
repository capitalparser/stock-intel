from dashboard.percentile import percentile_rank, severity_rank, worse_state, MIN_SERIES
from dashboard.percentile import DimensionSpec, dimension_state, RISK_HIGH, RISK_LOW


def test_percentile_rank_mid():
    assert percentile_rank(list(range(100)), 50) == 0.51  # 0..50 -> 51개 <= 50


def test_percentile_rank_extremes():
    assert percentile_rank(list(range(100)), 99) == 1.0
    assert percentile_rank(list(range(100)), -5) == 0.0


def test_percentile_rank_too_short_none():
    assert percentile_rank([1.0] * (MIN_SERIES - 1), 1.0) is None


def test_percentile_rank_ignores_none():
    assert percentile_rank([None] + list(range(100)), 50) == 0.51


def test_severity_and_worse():
    assert severity_rank("stressed") > severity_rank("warning") > severity_rank("supportive")
    assert worse_state("warning", "stressed") == "stressed"
    assert worse_state("supportive", "warning") == "warning"


def _band(center, n=60, spread=2.0):
    """center±spread 균등 60점."""
    return [center - spread + (2 * spread) * i / (n - 1) for i in range(n)]


def test_state_supportive_mid_percentile():
    spec = DimensionSpec("sentiment", "시장 심리", RISK_HIGH)
    assert dimension_state(spec, 15.0, _band(15.0)) == "supportive"


def test_state_warning_from_high_percentile():
    # 3.5..4.5 분포에서 4.40 -> 54/60=0.90 (0.85~0.95 -> warning), 가드레일 5.0 미도달
    spec = DimensionSpec("rates", "금리", RISK_HIGH, warn_guardrail=5.0)
    assert dimension_state(spec, 4.40, _band(4.0, spread=0.5)) == "warning"


def test_state_stressed_from_top_percentile():
    spec = DimensionSpec("rates", "금리", RISK_HIGH, warn_guardrail=5.0)
    assert dimension_state(spec, 4.49, _band(4.0, spread=0.5)) == "stressed"  # 0.98 >=0.95


def test_state_guardrail_forces_warning_below_percentile():
    # VIX 35±10 분포에서 21은 낮은 percentile이지만 20 가드레일이 warning 강제
    spec = DimensionSpec("sentiment", "시장 심리", RISK_HIGH, warn_guardrail=20.0)
    assert dimension_state(spec, 21.0, _band(35.0, spread=10.0)) == "warning"


def test_state_stress_guardrail():
    spec = DimensionSpec("oil", "유가", RISK_HIGH, stress_guardrail=100.0)
    assert dimension_state(spec, 101.0, _band(70.0, spread=10.0)) == "stressed"


def test_state_breadth_low_percentile_warns():
    # 40..80 분포에서 43.5 -> 6/60=0.10 (RISK_LOW 0.05~0.15 -> warning)
    spec = DimensionSpec("breadth", "시장 폭", RISK_LOW)
    assert dimension_state(spec, 43.5, _band(60.0, spread=20.0)) == "warning"


def test_state_unavailable_without_series_no_guardrail():
    spec = DimensionSpec("breadth", "시장 폭", RISK_LOW)
    assert dimension_state(spec, 50.0, []) == "unavailable"


def test_state_unavailable_without_series_guardrail_not_hit():
    spec = DimensionSpec("fx", "환율", RISK_HIGH, warn_guardrail=1450.0)
    assert dimension_state(spec, 1300.0, []) == "unavailable"  # 가드레일 미도달 -> unavailable


def test_state_guardrail_fires_without_series():
    spec = DimensionSpec("fx", "환율", RISK_HIGH, warn_guardrail=1450.0)
    assert dimension_state(spec, 1500.0, []) == "warning"
