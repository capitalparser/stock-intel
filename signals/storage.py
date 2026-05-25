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
        return [
            SignalEventRow(
                ticker=str(r["ticker"]),
                exchange=str(r["exchange"]),
                market=str(r["market"]),
                timeframe=str(r["timeframe"]),
                action=str(r["action"]),
                base_type=str(r["base_type"]),
                independence_status=str(r["independence_status"]),
                filter_status=str(r["filter_status"]),
                payload_json=str(r["payload_json"]),
                telegram_sent=bool(r["telegram_sent"]),
                received_at=int(r["received_at"]),
            )
            for r in rows
        ]

