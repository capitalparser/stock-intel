from dashboard.regime_history import append_today, load_history
from dashboard.regime_history import detect_transition


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


def _mkt(regime, axis_states=None):
    axis_states = axis_states or {}
    return {"market": "US", "regime": regime,
            "axis_reads": [{"dimension": d, "label": d, "state": s} for d, s in axis_states.items()]}


def test_transition_changed_with_axis_changes():
    prev = {"as_of": "2026-06-02", "us": _mkt("risk-on", {"breadth": "supportive", "rates": "supportive"})}
    today = _mkt("fragile rally", {"breadth": "warning", "rates": "supportive"})
    t = detect_transition([prev], today, "us")
    assert t["changed"] is True
    assert t["from"] == "risk-on"
    assert t["to"] == "fragile rally"
    assert {"dimension": "breadth", "from": "supportive", "to": "warning"} in t["axis_changes"]


def test_transition_streak_counts_consecutive():
    hist = [{"as_of": "2026-06-01", "us": _mkt("risk-on")},
            {"as_of": "2026-06-02", "us": _mkt("risk-on")}]
    t = detect_transition(hist, _mkt("risk-on"), "us")
    assert t["changed"] is False
    assert t["streak"] == 3


def test_transition_whipsaw_when_prior_streak_short():
    hist = [{"as_of": "2026-06-01", "us": _mkt("risk-on")},
            {"as_of": "2026-06-02", "us": _mkt("fragile rally")}]  # prior streak 1
    t = detect_transition(hist, _mkt("risk-off"), "us")
    assert t["changed"] is True
    assert t["whipsaw"] is True


def test_axis_changes_excludes_availability_noise():
    prev = {"as_of": "2026-06-02", "us": _mkt("conditional", {"breadth": "unavailable"})}
    today = _mkt("conditional", {"breadth": "warning"})
    t = detect_transition([prev], today, "us")
    assert t["axis_changes"] == []  # unavailable -> warning은 시그널 아님


def test_transition_no_history():
    t = detect_transition([], _mkt("risk-on"), "us")
    assert t["changed"] is False
    assert t["from"] is None
    assert t["streak"] == 1
    assert t["whipsaw"] is False
