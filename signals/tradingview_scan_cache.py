"""TTL cache for slow TradingView direct scan results."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Iterator

from signals.tradingview_direct import (
    TradingViewExcludedSignal,
    TradingViewLabelFlowItem,
    TradingViewLabelOutcome,
    TradingViewTableSnapshot,
)
from signals.tradingview_scan_runner import TradingViewScanResult


class TradingViewScanCache:
    def __init__(self, path: str | Path, *, ttl_seconds: int = 10 * 60) -> None:
        self._path = Path(path)
        self._ttl_seconds = ttl_seconds
        self._init()

    def get(self, *, symbols: list[str], context: dict) -> TradingViewScanResult | None:
        key = _cache_key(symbols=symbols, context=context)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT fetched_at, payload_json
                FROM tradingview_scan_cache
                WHERE cache_key = ?
                """,
                (key,),
            ).fetchone()
        if row is None:
            return None
        fetched_at, payload_json = row
        if int(time.time()) - int(fetched_at) > self._ttl_seconds:
            return None
        try:
            return _result_from_payload(json.loads(payload_json))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def set(self, *, symbols: list[str], context: dict, result: TradingViewScanResult) -> None:
        key = _cache_key(symbols=symbols, context=context)
        payload = json.dumps(_result_to_payload(result), ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tradingview_scan_cache(cache_key, fetched_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (key, int(time.time()), payload),
            )
            conn.commit()

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT fetched_at FROM tradingview_scan_cache").fetchall()
        now = int(time.time())
        total = len(rows)
        active = sum(1 for (fetched_at,) in rows if now - int(fetched_at) <= self._ttl_seconds)
        return {"total": total, "active": active, "expired": total - active, "ttl_seconds": self._ttl_seconds}

    def clear(self) -> int:
        with self._connect() as conn:
            deleted = conn.execute("DELETE FROM tradingview_scan_cache").rowcount
            conn.commit()
        return int(deleted or 0)

    def _init(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tradingview_scan_cache (
                    cache_key TEXT PRIMARY KEY,
                    fetched_at INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        try:
            yield conn
        finally:
            conn.close()


def _cache_key(*, symbols: list[str], context: dict) -> str:
    raw = json.dumps({"symbols": symbols, "context": context}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _result_to_payload(result: TradingViewScanResult) -> dict:
    return {
        "outcomes": [_as_payload(item) for item in result.outcomes],
        "exclusions": [_as_payload(item) for item in result.exclusions],
        "errors": [[symbol, error] for symbol, error in result.errors],
        "scanned": list(result.scanned),
        "label_flows": {
            symbol: [_as_payload(item) for item in items]
            for symbol, items in result.label_flows.items()
        },
        "table_snapshots": {
            symbol: (_as_payload(snapshot) if snapshot is not None else None)
            for symbol, snapshot in result.table_snapshots.items()
        },
    }


def _result_from_payload(payload: dict) -> TradingViewScanResult:
    return TradingViewScanResult(
        outcomes=[TradingViewLabelOutcome(**item) for item in payload.get("outcomes", [])],
        exclusions=[TradingViewExcludedSignal(**item) for item in payload.get("exclusions", [])],
        errors=[(str(symbol), str(error)) for symbol, error in payload.get("errors", [])],
        scanned=[str(item) for item in payload.get("scanned", [])],
        label_flows={
            symbol: [TradingViewLabelFlowItem(**item) for item in items]
            for symbol, items in payload.get("label_flows", {}).items()
        },
        table_snapshots={
            symbol: (TradingViewTableSnapshot(**snapshot) if snapshot is not None else None)
            for symbol, snapshot in payload.get("table_snapshots", {}).items()
        },
    )


def _as_payload(value) -> dict:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return dict(value)
