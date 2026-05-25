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
