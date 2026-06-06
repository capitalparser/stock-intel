"""Build, cache, and load the real-data snapshot.

A *snapshot* is the bridge between live providers and the dashboard input:
it fetches every universe ticker, computes peer-relative valuation, normalizes
the five lens metrics, records data-quality provenance, and serializes to JSON
so rendering is reproducible and rate-limit-free (cache-snapshot mode).

``build_snapshot`` takes injectable ``fetch``/``macro`` callables so it can be
unit-tested without network access.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from dashboard.macro_state import build_dual_regime as _build_dual_regime
from dashboard.metrics import METRIC_FIELDS, build_metrics
from dashboard.providers import RawStock, fetch_macro, fetch_raw_stock
from dashboard.providers.catalyst import fetch_catalysts
from dashboard.providers.independence_overlay import fetch_independence
from dashboard.providers.valuation import fetch_valuation
from dashboard.regime_history import DEFAULT_HISTORY_PATH, append_today, load_history

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[1] / "state" / "dashboard" / "cache"
LATEST_NAME = "snapshot-latest.json"


@dataclass(frozen=True)
class UniverseEntry:
    ticker: str
    peer_group: str = ""


def build_snapshot(
    universe: Iterable[UniverseEntry],
    *,
    fetch: Callable[[str], RawStock] = fetch_raw_stock,
    macro: Callable[[], dict] = fetch_macro,
    independence: Callable[[str], dict] = fetch_independence,
    catalysts: Callable[[str], list[dict]] = fetch_catalysts,
    valuation: Callable[[str], dict] = fetch_valuation,
    as_of: str | None = None,
    persist_regime_history: bool = False,
) -> dict:
    entries = list(universe)
    raws: dict[str, RawStock] = {}
    for entry in entries:
        raws[entry.ticker] = fetch(entry.ticker)

    peer_pe = _peer_pe_by_group(entries, raws)
    group_by_ticker = {e.ticker: e.peer_group for e in entries}
    valuation_reads = {
        entry.ticker: _safe_valuation(valuation, entry.ticker)
        for entry in entries
    }

    stocks: dict[str, dict] = {}
    for ticker, raw in raws.items():
        independence_read = _independence_read(ticker, independence)
        group = group_by_ticker.get(ticker, "")
        ppe = peer_pe.get(group)
        result = build_metrics(
            pe=raw.pe,
            peer_pe=ppe,
            pbr=raw.pbr,
            op_margin_pct=raw.op_margin_pct,
            ocf_positive=raw.ocf_positive,
            roe_pct=raw.roe_pct,
            revenue_growth_pct=raw.revenue_growth_pct,
            op_growth_pct=raw.op_growth_pct,
            net_flow_signal=raw.net_flow_signal,
            ma_trend=raw.ma_trend,
            bb_pct=raw.bb_pct,
            return_pct=raw.return_pct,
            volume_ratio=raw.volume_ratio,
        )
        missing_fields = list(result.missing)
        for field_name, value in (("price", raw.price), ("pe", raw.pe)):
            if value is None:
                missing_fields.append(field_name)
        stocks[ticker] = {
            "source": raw.source,
            "price": _round(raw.price, 2),
            "day_change_pct": _round(raw.day_change_pct, 2),
            "pe": _round(raw.pe, 1),
            "pbr": _round(raw.pbr, 2),
            "peer_pe": _round(ppe, 1),
            "peer_group": group,
            "short_ratio": _round(raw.short_ratio, 2),
            "net_flow_signal": _round(raw.net_flow_signal, 2),
            "closes": [round(float(c), 2) for c in (raw.closes or [])],
            "independence_status": str(independence_read.get("status") or ""),
            "auditor": independence_read.get("auditor") or "",
            "independence_reason": str(independence_read.get("reason") or ""),
            "catalysts": _safe_catalysts(catalysts, ticker),
            "expectation_verdict": str(valuation_reads.get(ticker, {}).get("verdict") or ""),
            "metrics": result.scores,
            "data_quality": {
                "missing": missing_fields,
                "proxy": result.proxy,
                "errors": raw.errors,
                "as_of": raw.as_of,
            },
        }

    resolved_as_of = as_of or _infer_as_of(raws) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    macro_payload = macro()
    _embed_dual_regime(
        macro_payload,
        as_of=resolved_as_of,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        persist_regime_history=persist_regime_history,
    )
    return {
        "as_of": resolved_as_of,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "macro": macro_payload,
        "valuation_expectations": list(valuation_reads.values()),
        "stocks": stocks,
    }


def _independence_read(ticker: str, independence: Callable[[str], dict]) -> dict:
    try:
        return independence(ticker) or {}
    except Exception as exc:  # pragma: no cover - defensive degrade
        return {
            "status": "DATA_MISSING",
            "auditor": "",
            "reason": f"독립성 overlay 실패: {type(exc).__name__}",
        }


def _safe_catalysts(ticker_catalysts: Callable[[str], list[dict]], ticker: str) -> list[dict]:
    try:
        return [dict(item) for item in (ticker_catalysts(ticker) or [])]
    except Exception:
        return []


def _safe_valuation(valuation: Callable[[str], dict], ticker: str) -> dict:
    try:
        out = dict(valuation(ticker) or {})
    except Exception as exc:  # pragma: no cover - defensive degrade
        out = {
            "ticker": ticker,
            "verdict": "데이터 부족",
            "reason": f"밸류에이션 기대치 overlay 실패: {type(exc).__name__}",
            "read": "v1: 성장·FCF only (가이던스/리비전 미반영) · 데이터 부족",
            "data_gaps": ["밸류에이션 기대치 provider 실패"],
        }
    out.setdefault("ticker", ticker)
    out.setdefault("verdict", "데이터 부족")
    out.setdefault("data_gaps", [])
    return out


def _peer_pe_by_group(
    entries: list[UniverseEntry], raws: dict[str, RawStock]
) -> dict[str, float]:
    by_group: dict[str, list[float]] = {}
    for entry in entries:
        raw = raws.get(entry.ticker)
        if raw and raw.pe and raw.pe > 0:
            by_group.setdefault(entry.peer_group, []).append(raw.pe)
    return {
        group: round(statistics.median(values), 1)
        for group, values in by_group.items()
        if values
    }


def _infer_as_of(raws: dict[str, RawStock]) -> str | None:
    dates = sorted(r.as_of for r in raws.values() if r.as_of)
    return dates[-1] if dates else None


def build_dual_regime(us_indicators: list[dict], kr_indicators: list[dict], *, as_of: str) -> dict:
    return _build_dual_regime(
        us_indicators,
        kr_indicators,
        history=load_history(_history_path()),
        as_of=as_of,
    )


def _embed_dual_regime(
    macro_payload: dict,
    *,
    as_of: str,
    generated_at: str,
    persist_regime_history: bool,
) -> None:
    us_indicators = macro_payload.get("_us_indicators") or macro_payload.get("market_indicators") or []
    kr_indicators = macro_payload.get("_kr_indicators") or []
    if not us_indicators and not kr_indicators:
        return
    dual = build_dual_regime(us_indicators, kr_indicators, as_of=as_of)
    macro_payload["dual_regime"] = dual
    if persist_regime_history:
        append_today(
            {
                "as_of": as_of,
                "us": dual["us"],
                "kr": dual["kr"],
                "generated_at": generated_at,
            },
            _history_path(),
        )


def _history_path() -> Path:
    return DEFAULT_HISTORY_PATH


# --------------------------------------------------------------------------- #
# Cache I/O
# --------------------------------------------------------------------------- #
def save_snapshot(snapshot: dict, cache_dir: str | Path = DEFAULT_CACHE_DIR) -> Path:
    target = Path(cache_dir)
    target.mkdir(parents=True, exist_ok=True)
    dated = target / f"snapshot-{snapshot['as_of']}.json"
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    dated.write_text(payload, encoding="utf-8")
    (target / LATEST_NAME).write_text(payload, encoding="utf-8")
    return dated


def load_latest_snapshot(cache_dir: str | Path = DEFAULT_CACHE_DIR) -> dict | None:
    target = Path(cache_dir)
    latest = target / LATEST_NAME
    if latest.exists():
        return json.loads(latest.read_text(encoding="utf-8"))
    candidates = sorted(target.glob("snapshot-*.json"))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def _round(value, ndigits):
    if value is None:
        return None
    return round(float(value), ndigits)
