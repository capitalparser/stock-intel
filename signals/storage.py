"""SQLite storage for TradingView signal events."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from signals.payload import TradingViewSignal

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    exchange TEXT NOT NULL,
    market TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    action TEXT NOT NULL,
    base_type TEXT NOT NULL,
    independence_status TEXT NOT NULL,
    filter_status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    telegram_sent INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_signal_events_received
    ON signal_events(received_at DESC);
CREATE TABLE IF NOT EXISTS active_signal_states (
    ticker TEXT PRIMARY KEY,
    exchange TEXT NOT NULL,
    market TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    action TEXT NOT NULL,
    base_type TEXT NOT NULL,
    independence_status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    activated_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_active_signal_states_lookup
    ON active_signal_states(active, market, expires_at DESC);
"""


@dataclass(frozen=True)
class SignalEventRow:
    ticker: str
    exchange: str
    market: str
    timeframe: str
    action: str
    base_type: str
    independence_status: str
    filter_status: str
    payload_json: str
    telegram_sent: bool
    received_at: int


@dataclass(frozen=True)
class ActiveSignalRow:
    ticker: str
    exchange: str
    market: str
    timeframe: str
    action: str
    base_type: str
    independence_status: str
    payload_json: str
    activated_at: int
    updated_at: int
    expires_at: int
    active: bool


class SignalStore:
    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._init()

    def _init(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def put_event(
        self,
        *,
        signal: TradingViewSignal,
        market: str,
        independence_status: str,
        filter_status: str,
        telegram_sent: bool,
        received_at: int | None = None,
    ) -> None:
        ts = int(received_at if received_at is not None else time.time())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO signal_events("
                "received_at, ticker, exchange, market, timeframe, action, base_type, "
                "independence_status, filter_status, payload_json, telegram_sent"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ts,
                    signal.ticker,
                    signal.exchange,
                    market,
                    signal.timeframe,
                    signal.action,
                    signal.base_type(),
                    independence_status,
                    filter_status,
                    signal.model_dump_json(),
                    1 if telegram_sent else 0,
                ),
            )
            conn.commit()

    def recent(self, limit: int = 20) -> list[SignalEventRow]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM signal_events ORDER BY received_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_event(r) for r in rows]

    def recent_since(self, since: int, limit: int = 50) -> list[SignalEventRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM signal_events
                WHERE received_at >= ?
                ORDER BY received_at DESC, id DESC
                LIMIT ?
                """,
                (since, limit),
            ).fetchall()
        return [_row_to_event(r) for r in rows]

    def latest_for_ticker(self, ticker: str) -> SignalEventRow | None:
        candidates = {ticker}
        if ticker.isdigit() and len(ticker) == 6:
            candidates.add(f"KRX:{ticker}")
        placeholders = ",".join("?" for _ in candidates)
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT * FROM signal_events
                WHERE ticker IN ({placeholders})
                ORDER BY received_at DESC, id DESC
                LIMIT 1
                """,
                tuple(candidates),
            ).fetchone()
        return _row_to_event(row) if row is not None else None

    def upsert_active_signal(
        self,
        *,
        signal: TradingViewSignal,
        market: str,
        independence_status: str,
        activated_at: int | None = None,
        ttl_seconds: int = 8 * 3600,
    ) -> None:
        ts = int(activated_at if activated_at is not None else time.time())
        expires_at = ts + ttl_seconds
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO active_signal_states(
                    ticker, exchange, market, timeframe, action, base_type,
                    independence_status, payload_json, activated_at, updated_at, expires_at, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(ticker) DO UPDATE SET
                    exchange=excluded.exchange,
                    market=excluded.market,
                    timeframe=excluded.timeframe,
                    action=excluded.action,
                    base_type=excluded.base_type,
                    independence_status=excluded.independence_status,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at,
                    expires_at=excluded.expires_at,
                    active=1
                """,
                (
                    signal.ticker,
                    signal.exchange,
                    market,
                    signal.timeframe,
                    signal.action,
                    signal.base_type(),
                    independence_status,
                    signal.model_dump_json(),
                    ts,
                    ts,
                    expires_at,
                ),
            )
            conn.commit()

    def close_active_signal(self, ticker: str, closed_at: int | None = None) -> None:
        candidates = {ticker}
        if ticker.isdigit() and len(ticker) == 6:
            candidates.add(f"KRX:{ticker}")
        placeholders = ",".join("?" for _ in candidates)
        ts = int(closed_at if closed_at is not None else time.time())
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE active_signal_states
                SET active=0, updated_at=?, expires_at=?
                WHERE ticker IN ({placeholders})
                """,
                (ts, ts, *tuple(candidates)),
            )
            conn.commit()

    def active_signals(self, now: int | None = None, limit: int = 50) -> list[ActiveSignalRow]:
        current = int(now if now is not None else time.time())
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM active_signal_states
                WHERE active = 1 AND expires_at >= ?
                ORDER BY updated_at DESC, activated_at DESC
                LIMIT ?
                """,
                (current, limit),
            ).fetchall()
        return [_row_to_active(r) for r in rows]


def _row_to_event(row: sqlite3.Row) -> SignalEventRow:
    return SignalEventRow(
        ticker=str(row["ticker"]),
        exchange=str(row["exchange"]),
        market=str(row["market"]),
        timeframe=str(row["timeframe"]),
        action=str(row["action"]),
        base_type=str(row["base_type"]),
        independence_status=str(row["independence_status"]),
        filter_status=str(row["filter_status"]),
        payload_json=str(row["payload_json"]),
        telegram_sent=bool(row["telegram_sent"]),
        received_at=int(row["received_at"]),
    )


def _row_to_active(row: sqlite3.Row) -> ActiveSignalRow:
    return ActiveSignalRow(
        ticker=str(row["ticker"]),
        exchange=str(row["exchange"]),
        market=str(row["market"]),
        timeframe=str(row["timeframe"]),
        action=str(row["action"]),
        base_type=str(row["base_type"]),
        independence_status=str(row["independence_status"]),
        payload_json=str(row["payload_json"]),
        activated_at=int(row["activated_at"]),
        updated_at=int(row["updated_at"]),
        expires_at=int(row["expires_at"]),
        active=bool(row["active"]),
    )
