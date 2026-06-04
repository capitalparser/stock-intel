from dashboard.percentile import percentile_rank, severity_rank, worse_state, MIN_SERIES


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
