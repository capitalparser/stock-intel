from dashboard.regime_history import append_today, load_history


def _rec(as_of, us_regime, kr_regime):
    return {"as_of": as_of, "generated_at": f"{as_of}T00:00:00+00:00",
            "us": {"market": "US", "regime": us_regime, "axis_reads": []},
            "kr": {"market": "KR", "regime": kr_regime, "axis_reads": []}}


def test_append_and_load_roundtrip(tmp_path):
    p = tmp_path / "regime_history.jsonl"
    append_today(_rec("2026-06-02", "risk-on", "conditional"), p)
    append_today(_rec("2026-06-03", "fragile rally", "risk-off"), p)
    hist = load_history(p)
    assert [r["as_of"] for r in hist] == ["2026-06-02", "2026-06-03"]
    assert hist[-1]["us"]["regime"] == "fragile rally"


def test_same_day_overwrites(tmp_path):
    p = tmp_path / "regime_history.jsonl"
    append_today(_rec("2026-06-03", "risk-on", "risk-on"), p)
    append_today(_rec("2026-06-03", "conditional", "risk-off"), p)
    hist = load_history(p)
    assert len(hist) == 1
    assert hist[0]["us"]["regime"] == "conditional"


def test_load_missing_returns_empty(tmp_path):
    assert load_history(tmp_path / "nope.jsonl") == []
