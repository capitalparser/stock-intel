"""Lookup Market Insights entry for a single ticker, for the bot stock report.

Combines two sources:

* **Text payload** — ``build_market_insights_payload()`` scans
  ``02_Areas/Market_Insights/**/*.md`` and merges with ``SAMPLE_DASHBOARD``.
  Provides ``thesis`` / ``bull_case`` / ``bear_case`` / ``lens_ids`` /
  ``source_refs`` per ticker.
* **Snapshot metrics** — ``load_latest_snapshot()`` reads the cached real-data
  snapshot. Provides per-ticker ``metrics`` (valuation / quality / growth /
  revision / momentum). Optional — falls back to ``None`` if the snapshot file
  is missing.

Both reads are expensive (vault scan + JSON load), so the indexed result is
cached in module memory with a short TTL.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dashboard.market_insights import (
    DEFAULT_MARKET_INSIGHTS_DIR,
    build_market_insights_payload,
)
from dashboard.snapshot import DEFAULT_CACHE_DIR, load_latest_snapshot


DEFAULT_TTL_SECONDS = 300


@dataclass(frozen=True)
class InsightCard:
    ticker: str
    company: str
    sector: str
    thesis: str
    bull_case: tuple[str, ...]
    bear_case: tuple[str, ...]
    lens_ids: tuple[str, ...]
    source_refs: tuple[str, ...]
    metrics: dict[str, float] | None  # None when snapshot is unavailable


_CacheEntry = tuple[float, dict[str, InsightCard]]
_INDEX_CACHE: dict[tuple[str, str], _CacheEntry] = {}


def lookup_insight(
    ticker: str,
    *,
    insights_dir: str | Path = DEFAULT_MARKET_INSIGHTS_DIR,
    snapshot_cache_dir: str | Path = DEFAULT_CACHE_DIR,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> InsightCard | None:
    """Return the Market Insights entry for ``ticker``, or ``None`` if absent."""
    index = _get_index(
        insights_dir=insights_dir,
        snapshot_cache_dir=snapshot_cache_dir,
        ttl_seconds=ttl_seconds,
        now=now,
    )
    return index.get(str(ticker))


def clear_cache() -> None:
    """Drop the in-memory index cache. Used by tests."""
    _INDEX_CACHE.clear()


def _get_index(
    *,
    insights_dir: str | Path,
    snapshot_cache_dir: str | Path,
    ttl_seconds: float,
    now: float | None,
) -> dict[str, InsightCard]:
    current = time.monotonic() if now is None else now
    key = (str(insights_dir), str(snapshot_cache_dir))
    entry = _INDEX_CACHE.get(key)
    if entry is not None and current - entry[0] < ttl_seconds:
        return entry[1]
    index = _build_index(
        insights_dir=insights_dir,
        snapshot_cache_dir=snapshot_cache_dir,
    )
    _INDEX_CACHE[key] = (current, index)
    return index


def _build_index(
    *,
    insights_dir: str | Path,
    snapshot_cache_dir: str | Path,
) -> dict[str, InsightCard]:
    payload = build_market_insights_payload(
        insights_dir,
        include_kr_screen=False,
        include_policy_lens=False,
    )
    snapshot = _load_snapshot(snapshot_cache_dir)
    snapshot_stocks: dict[str, dict[str, Any]] = (
        snapshot.get("stocks", {}) if snapshot else {}
    )

    cards: dict[str, InsightCard] = {}
    for stock in payload.get("stocks", []):
        ticker = str(stock.get("ticker", "")).strip()
        if not ticker:
            continue
        snap = snapshot_stocks.get(ticker) or {}
        snap_metrics = snap.get("metrics") if isinstance(snap, dict) else None
        metrics: dict[str, float] | None
        if snap_metrics:
            metrics = {str(k): float(v) for k, v in snap_metrics.items()}
        else:
            metrics = None
        cards[ticker] = InsightCard(
            ticker=ticker,
            company=str(stock.get("company", "")),
            sector=str(stock.get("sector", "")),
            thesis=str(stock.get("thesis", "")).strip(),
            bull_case=tuple(str(x) for x in stock.get("bull_case", []) if x),
            bear_case=tuple(str(x) for x in stock.get("bear_case", []) if x),
            lens_ids=tuple(str(x) for x in stock.get("lens_ids", []) if x),
            source_refs=tuple(str(x) for x in stock.get("source_refs", []) if x),
            metrics=metrics,
        )
    return cards


def _load_snapshot(cache_dir: str | Path) -> dict | None:
    try:
        return load_latest_snapshot(cache_dir)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
_METRIC_LABELS: tuple[tuple[str, str], ...] = (
    ("valuation", "V"),
    ("quality", "Q"),
    ("growth", "G"),
    ("revision", "R"),
    ("momentum", "M"),
)


def format_insight_section(
    card: InsightCard | None,
    *,
    max_bull: int = 2,
    max_bear: int = 1,
    max_sources: int = 2,
) -> str:
    """Render the insight section appended to the stock lookup reply.

    Returns a non-empty string. Callers append it directly.
    """
    if card is None:
        return "💡 인사이트\nMarket Insights 등재 없음"

    lines: list[str] = ["💡 인사이트"]
    if card.source_refs:
        sources = " · ".join(card.source_refs[:max_sources])
        lines.append(f"출처: {sources}")
    if card.lens_ids:
        lines.append(f"렌즈: {', '.join(card.lens_ids)}")
    if card.thesis:
        lines.append(f"논지: {card.thesis}")
    for bullet in card.bull_case[:max_bull]:
        lines.append(f"강세: {bullet}")
    for bullet in card.bear_case[:max_bear]:
        lines.append(f"약세: {bullet}")
    lines.append(f"점수: {_format_metrics(card.metrics)}")
    return "\n".join(lines)


def _format_metrics(metrics: dict[str, float] | None) -> str:
    if not metrics:
        return "스냅샷 미상"
    parts: list[str] = []
    for key, label in _METRIC_LABELS:
        if key in metrics:
            parts.append(f"{label}{int(round(metrics[key]))}")
    return "·".join(parts) if parts else "스냅샷 미상"
