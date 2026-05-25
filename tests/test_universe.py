import json
from pathlib import Path

from signals.universe import (
    build_universe_snapshot,
    format_universe_summary,
    load_universe_snapshot,
    save_universe_snapshot,
    symbol_in_universe,
    sync_universe_from_tradingview,
)


FIXTURES = Path(__file__).parent / "fixtures"


def load_watchlists() -> dict:
    return json.loads(
        (FIXTURES / "tradingview_watchlists_all_sample.json").read_text(encoding="utf-8")
    )


def test_build_universe_snapshot_deduplicates_all_watchlists_and_classifies_symbols():
    snapshot = build_universe_snapshot(load_watchlists()["lists"], fetched_at="2026-05-25T00:00:00Z")

    assert snapshot.total_symbols == 9
    assert snapshot.counts_by_market["KR"] == 2
    assert snapshot.counts_by_market["US"] == 3
    assert snapshot.counts_by_market["FUTURES"] == 1
    assert snapshot.counts_by_asset_type["CRYPTO"] == 2
    assert snapshot.counts_by_asset_type["INDEX"] == 1
    assert snapshot.watchlists["국장"].symbol_count == 3
    assert snapshot.symbols["KRX:005930"].watchlists == ["관심", "국장"]
    assert snapshot.symbols["KRX:005930"].audit_lookup_supported is True
    assert snapshot.symbols["KRX:S0X1!"].audit_lookup_supported is False
    assert snapshot.symbols["NASDAQ:AAPL"].market == "US"


def test_universe_snapshot_roundtrip_json(tmp_path):
    path = tmp_path / "universe_snapshot.json"
    snapshot = build_universe_snapshot(load_watchlists()["lists"], fetched_at="2026-05-25T00:00:00Z")

    save_universe_snapshot(snapshot, path)
    loaded = load_universe_snapshot(path)

    assert loaded is not None
    assert loaded.total_symbols == snapshot.total_symbols
    assert loaded.symbols["NYSE:DELL"].watchlists == ["관심"]


def test_format_universe_summary_reports_watchlists_and_markets():
    snapshot = build_universe_snapshot(load_watchlists()["lists"], fetched_at="2026-05-25T00:00:00Z")

    text = format_universe_summary(snapshot)

    assert "TradingView Universe" in text
    assert "전체 심볼: 9" in text
    assert "국장: 3" in text
    assert "관심: 5" in text
    assert "KR 2" in text
    assert "US 3" in text


def test_symbol_in_universe_matches_plain_and_prefixed_korean_tickers():
    snapshot = build_universe_snapshot(load_watchlists()["lists"], fetched_at="2026-05-25T00:00:00Z")

    assert symbol_in_universe("005930", snapshot) is True
    assert symbol_in_universe("KRX:005930", snapshot) is True
    assert symbol_in_universe("NASDAQ:AAPL", snapshot) is True
    assert symbol_in_universe("NASDAQ:MSFT", snapshot) is False


def test_sync_universe_from_tradingview_saves_snapshot(tmp_path, monkeypatch):
    output = json.dumps(load_watchlists())

    class Completed:
        stdout = output

    def fake_run(*args, **kwargs):
        assert args[0][0] == "node"
        assert kwargs["cwd"] == "/tmp/tradingview-mcp"
        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)
    path = tmp_path / "universe.json"

    snapshot = sync_universe_from_tradingview(
        mcp_dir="/tmp/tradingview-mcp",
        output_path=path,
        fetched_at="2026-05-25T00:00:00Z",
    )

    assert snapshot.total_symbols == 9
    assert load_universe_snapshot(path).total_symbols == 9
