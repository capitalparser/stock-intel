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


def _axis_states(market_record: dict) -> dict[str, str]:
    return {a["dimension"]: a["state"] for a in market_record.get("axis_reads", [])}


def detect_transition(history: list[dict], today_market: dict, market: str) -> dict:
    """`history`: 오늘을 제외한 이전 레코드들. `market` in {'us','kr'}."""
    prior = [r for r in history if market in r]
    to_regime = today_market["regime"]
    if not prior:
        return {"changed": False, "from": None, "to": to_regime,
                "streak": 1, "whipsaw": False, "axis_changes": []}

    prev = prior[-1][market]
    from_regime = prev.get("regime")
    changed = from_regime != to_regime

    prior_streak = 0
    for r in reversed(prior):
        if r[market].get("regime") == from_regime:
            prior_streak += 1
        else:
            break
    streak = 1 if changed else prior_streak + 1
    whipsaw = changed and prior_streak <= 1

    prev_axis = _axis_states(prev)
    today_axis = _axis_states(today_market)
    axis_changes = [
        {"dimension": d, "from": prev_axis[d], "to": today_axis[d]}
        for d in today_axis
        if prev_axis.get(d) not in (None, "unavailable")
        and today_axis[d] != "unavailable"
        and prev_axis[d] != today_axis[d]
    ]
    return {"changed": changed, "from": from_regime, "to": to_regime,
            "streak": streak, "whipsaw": whipsaw, "axis_changes": axis_changes}
