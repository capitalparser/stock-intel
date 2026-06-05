"""Export the Lane B React cockpit dashboard contract.

This combines the curated market-insights narrative with the latest real-data
snapshot overlay, then serializes the screened Dashboard into the JSON contract
consumed by the planned React cockpit.

Run:
    uv run python scripts/export_dashboard_json.py
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from dashboard.live import overlay_snapshot
from dashboard.market_insights import build_market_insights_payload
from dashboard.models import Dashboard, parse_dashboard_input
from dashboard.screeners import build_dashboard
from dashboard.snapshot import DEFAULT_CACHE_DIR, load_latest_snapshot

DASHBOARD_LATEST_NAME = "dashboard-latest.json"
DEFAULT_OUTPUT_PATH = DEFAULT_CACHE_DIR / DASHBOARD_LATEST_NAME

REQUIRED_CANDIDATE_KEYS = (
    "ticker",
    "company",
    "sector",
    "score",
    "status",
    "linked_lenses",
    "strongest_lens",
    "evidence",
    "gaps",
    "risk_flags",
    "thesis",
    "bull_case",
    "bear_case",
    "next_action",
    "price",
    "day_change_pct",
    "pe",
    "peer_pe",
    "peer_group",
    "independence_status",
    "auditor",
    "catalysts",
    "expectation_verdict",
    "price_series",
)


def build_export_payload(
    *,
    insights_dir: str | Path | None = None,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    market_payload: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the React cockpit JSON contract.

    ``market_payload`` and ``snapshot`` are injectable so tests can validate the
    contract without network calls or fixture files.
    """
    payload = (
        market_payload
        if market_payload is not None
        else build_market_insights_payload() if insights_dir is None
        else build_market_insights_payload(insights_dir)
    )
    snapshot_payload = snapshot if snapshot is not None else load_latest_snapshot(cache_dir)
    if snapshot_payload:
        overlay_snapshot(payload, snapshot_payload)

    dashboard_input = parse_dashboard_input(payload)
    dashboard = build_dashboard(dashboard_input)
    return serialize_dashboard(dashboard, payload=payload, snapshot=snapshot_payload or {})


def serialize_dashboard(
    dashboard: Dashboard,
    *,
    payload: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    stocks_by_ticker = {str(stock.get("ticker")): stock for stock in payload.get("stocks", [])}
    snapshot_stocks = snapshot.get("stocks") or {}
    candidates = [
        _serialize_candidate(
            candidate,
            stock_payload=stocks_by_ticker.get(candidate.ticker, {}),
            snapshot_stock=snapshot_stocks.get(candidate.ticker, {}),
        )
        for candidate in dashboard.candidates
    ]
    return {
        "as_of": dashboard.as_of,
        "price_time": dashboard.price_time,
        "dual_regime": _to_jsonable(dashboard.dual_regime),
        "market_indicators": _to_jsonable(dashboard.market_indicators),
        "lenses": [_serialize_lens(lens) for lens in dashboard.lenses],
        "candidates": candidates,
        "valuation_expectations": _to_jsonable(dashboard.valuation_expectations or []),
    }


def write_dashboard_json(payload: dict[str, Any], output_path: str | Path = DEFAULT_OUTPUT_PATH) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _serialize_candidate(candidate, *, stock_payload: dict[str, Any], snapshot_stock: dict[str, Any]) -> dict[str, Any]:
    item = {
        "ticker": candidate.ticker,
        "company": candidate.company,
        "sector": candidate.sector,
        "score": candidate.score,
        "status": _to_jsonable(candidate.status),
        "linked_lenses": [_serialize_linked_lens(lens) for lens in candidate.linked_lenses],
        "strongest_lens": candidate.strongest_lens,
        "evidence": list(candidate.evidence),
        "gaps": list(candidate.gaps),
        "risk_flags": list(candidate.risk_flags),
        "thesis": candidate.thesis,
        "bull_case": list(candidate.bull_case),
        "bear_case": list(candidate.bear_case),
        "next_action": candidate.next_action,
        "price": candidate.price,
        "day_change_pct": candidate.day_change_pct,
        "pe": candidate.pe,
        "peer_pe": candidate.peer_pe,
        "peer_group": candidate.peer_group,
        "independence_status": candidate.independence_status,
        "auditor": candidate.auditor,
        "catalysts": _to_jsonable(candidate.catalysts or []),
        "expectation_verdict": candidate.expectation_verdict,
        "price_series": _price_series(stock_payload, snapshot_stock),
    }
    return {key: item[key] for key in REQUIRED_CANDIDATE_KEYS}


def _serialize_lens(lens) -> dict[str, Any]:
    item = _to_jsonable(lens)
    item["kind"] = _to_jsonable(lens.kind)
    return item


def _serialize_linked_lens(lens) -> dict[str, str]:
    return {"id": str(lens.id), "name": str(lens.name)}


def _price_series(stock_payload: dict[str, Any], snapshot_stock: dict[str, Any]) -> list[float]:
    for source in (stock_payload, snapshot_stock):
        values = source.get("price_series") or source.get("closes") or source.get("series")
        if values:
            return [float(value) for value in list(values)[-60:] if value is not None]
    return []


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _to_jsonable(val) for key, val in asdict(value).items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(val) for key, val in value.items()}
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the Lane B React dashboard JSON contract.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    args = parser.parse_args()

    payload = build_export_payload(cache_dir=args.cache_dir)
    path = write_dashboard_json(payload, args.output)
    print(f"Saved dashboard JSON: {path}")
    print(f"Top-level keys: {', '.join(payload.keys())}")
    print(f"Candidates: {len(payload['candidates'])}")


if __name__ == "__main__":
    main()
