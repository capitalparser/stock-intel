"""Dual-regime daily history (JSONL, one record per business day) + transitions."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_HISTORY_PATH = (
    Path(__file__).resolve().parents[1] / "state" / "dashboard" / "regime_history.jsonl"
)


def load_history(path: str | Path = DEFAULT_HISTORY_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    records = [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]
    records.sort(key=lambda r: r.get("as_of", ""))
    return records


def append_today(record: dict, path: str | Path = DEFAULT_HISTORY_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = {r["as_of"]: r for r in load_history(p)}
    existing[record["as_of"]] = record  # same day overwrite
    ordered = [existing[k] for k in sorted(existing)]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ordered) + "\n", encoding="utf-8")
