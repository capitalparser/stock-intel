"""Snapshot tests: peer-PE median, build orchestration, cache I/O (no network)."""

from dashboard.providers.base import RawStock
from dashboard.snapshot import (
    UniverseEntry,
    build_snapshot,
    load_latest_snapshot,
    save_snapshot,
)


def _fake_fetch_factory(table):
    def fetch(ticker):
        return table[ticker]
    return fetch


def _empty_macro():
    return {"market_indicators": [], "regime": {}, "errors": []}


def test_peer_pe_is_group_median():
    table = {
        "A": RawStock("A", "US", pe=10, op_margin_pct=20, as_of="2026-05-30"),
        "B": RawStock("B", "US", pe=20, op_margin_pct=20, as_of="2026-05-30"),
        "C": RawStock("C", "US", pe=30, op_margin_pct=20, as_of="2026-05-30"),
    }
    universe = [
        UniverseEntry("A", "chips"),
        UniverseEntry("B", "chips"),
        UniverseEntry("C", "chips"),
    ]
    snap = build_snapshot(universe, fetch=_fake_fetch_factory(table), macro=_empty_macro)
    # median of [10,20,30] = 20 for every chips member
    for t in ("A", "B", "C"):
        assert snap["stocks"][t]["peer_pe"] == 20.0


def test_build_snapshot_records_missing_fields():
    table = {
        "X": RawStock("X", "US"),  # nothing populated
    }
    snap = build_snapshot(
        [UniverseEntry("X", "grp")], fetch=_fake_fetch_factory(table), macro=_empty_macro
    )
    dq = snap["stocks"]["X"]["data_quality"]
    assert "price" in dq["missing"]
    assert "pe" in dq["missing"]
    # all five metric fields default to neutral and are flagged missing
    for metric in ("valuation", "quality", "growth", "revision", "momentum"):
        assert snap["stocks"]["X"]["metrics"][metric] == 50.0


def test_build_snapshot_real_values_clear_gaps():
    table = {
        "GOOD": RawStock(
            "GOOD", "US", price=100.0, day_change_pct=1.2, pe=18, pbr=3.0,
            op_margin_pct=30, ocf_positive=True, roe_pct=20,
            revenue_growth_pct=15, op_growth_pct=18, net_flow_signal=1.0,
            ma_trend="정배열", bb_pct=60, return_pct=8, volume_ratio=1.3,
            as_of="2026-05-30",
        ),
        "PEER": RawStock("PEER", "US", pe=22, as_of="2026-05-30"),
    }
    snap = build_snapshot(
        [UniverseEntry("GOOD", "grp"), UniverseEntry("PEER", "grp")],
        fetch=_fake_fetch_factory(table),
        macro=_empty_macro,
    )
    good = snap["stocks"]["GOOD"]
    assert good["price"] == 100.0
    assert good["peer_pe"] == 20.0  # median(18,22)
    assert good["data_quality"]["missing"] == []
    assert good["data_quality"]["proxy"] == ["revision"]
    assert snap["as_of"] == "2026-05-30"


def test_save_and_load_roundtrip(tmp_path):
    table = {"A": RawStock("A", "US", price=1.0, pe=10, as_of="2026-05-30")}
    snap = build_snapshot(
        [UniverseEntry("A", "g")], fetch=_fake_fetch_factory(table), macro=_empty_macro
    )
    path = save_snapshot(snap, tmp_path)
    assert path.exists()
    assert (tmp_path / "snapshot-latest.json").exists()

    loaded = load_latest_snapshot(tmp_path)
    assert loaded["stocks"]["A"]["price"] == 1.0
    assert load_latest_snapshot(tmp_path / "does_not_exist") is None


def test_build_snapshot_carries_macro_state_payload():
    table = {"TEST": RawStock("TEST", "US", price=10.0, pe=12.0, as_of="2026-06-03")}

    snapshot = build_snapshot(
        [UniverseEntry("TEST", "fixture")],
        fetch=_fake_fetch_factory(table),
        macro=lambda: {
            "market_indicators": [],
            "regime": {},
            "macro_state": {
                "current_state": "conditional",
                "why_it_matters": "fixture",
                "next_action": "fixture",
                "indicator_reads": [],
                "issues": [],
                "watchlist_impact": {},
                "data_gaps": [],
            },
            "errors": [],
        },
        as_of="2026-06-03",
    )

    assert snapshot["macro"]["macro_state"]["current_state"] == "conditional"
