"""Persist and report Lazy Alpha state transitions."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from signals.tradingview_direct import (
    TradingViewExcludedSignal,
    TradingViewLabelOutcome,
    TradingViewTableSnapshot,
    evaluate_lazy_alpha_state,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lazy_alpha_symbol_states (
    symbol TEXT PRIMARY KEY,
    market TEXT NOT NULL,
    state_key TEXT NOT NULL,
    label TEXT NOT NULL,
    label_date TEXT NOT NULL,
    verdict TEXT NOT NULL,
    action TEXT NOT NULL,
    observed_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lazy_alpha_symbol_states_observed
    ON lazy_alpha_symbol_states(observed_at DESC);
"""


@dataclass(frozen=True)
class SymbolLazyAlphaState:
    symbol: str
    market: str
    state_key: str
    label: str
    label_date: str
    verdict: str
    action: str


@dataclass(frozen=True)
class LazyAlphaStateTransition:
    symbol: str
    market: str
    previous_state: str
    current_state: str
    previous_label: str
    current_label: str
    previous_label_date: str
    current_label_date: str
    verdict: str
    action: str
    observed_at: int


class LazyAlphaTransitionStore:
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

    def record_states(
        self,
        states: list[SymbolLazyAlphaState],
        *,
        observed_at: int | None = None,
    ) -> list[LazyAlphaStateTransition]:
        ts = int(observed_at if observed_at is not None else time.time())
        transitions: list[LazyAlphaStateTransition] = []
        with self._connect() as conn:
            for state in states:
                previous = conn.execute(
                    "SELECT * FROM lazy_alpha_symbol_states WHERE symbol = ?",
                    (state.symbol,),
                ).fetchone()
                if previous is not None and _state_changed(previous, state):
                    transitions.append(
                        LazyAlphaStateTransition(
                            symbol=state.symbol,
                            market=state.market,
                            previous_state=str(previous["state_key"]),
                            current_state=state.state_key,
                            previous_label=str(previous["label"]),
                            current_label=state.label,
                            previous_label_date=str(previous["label_date"]),
                            current_label_date=state.label_date,
                            verdict=state.verdict,
                            action=state.action,
                            observed_at=ts,
                        )
                    )
                conn.execute(
                    """
                    INSERT INTO lazy_alpha_symbol_states(
                        symbol, market, state_key, label, label_date, verdict, action, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        market=excluded.market,
                        state_key=excluded.state_key,
                        label=excluded.label,
                        label_date=excluded.label_date,
                        verdict=excluded.verdict,
                        action=excluded.action,
                        observed_at=excluded.observed_at
                    """,
                    (
                        state.symbol,
                        state.market,
                        state.state_key,
                        state.label,
                        state.label_date,
                        state.verdict,
                        state.action,
                        ts,
                    ),
                )
            conn.commit()
        return transitions


def build_symbol_states_from_scan(result) -> list[SymbolLazyAlphaState]:
    states: dict[str, SymbolLazyAlphaState] = {}
    table_snapshots = getattr(result, "table_snapshots", {}) or {}
    for outcome in getattr(result, "outcomes", []):
        states[outcome.symbol] = _state_from_outcome(
            outcome,
            table_snapshots.get(outcome.symbol),
        )
    for exclusion in _latest_exclusions_by_symbol(getattr(result, "exclusions", [])):
        if exclusion.symbol not in states:
            states[exclusion.symbol] = _state_from_exclusion(exclusion)
    for symbol in getattr(result, "scanned", []):
        if symbol in states:
            continue
        flows = getattr(result, "label_flows", {}).get(symbol, [])
        states[symbol] = _state_from_flow(symbol, flows)
    return list(states.values())


def format_transition_report(
    transitions: list[LazyAlphaStateTransition],
    *,
    scanned_count: int,
    errors: list[tuple[str, str]],
    limit: int = 12,
) -> str:
    lines = [
        "🔔 Lazy Alpha 상태 전환",
        f"스캔: {scanned_count}종목 · 전환: {len(transitions)}건 · 오류: {len(errors)}건",
    ]
    if not transitions:
        lines.extend(["", "새로 알릴 상태 전환이 없습니다."])
    for index, item in enumerate(transitions[:limit], start=1):
        lines.extend(
            [
                "",
                f"{index}. {item.symbol}",
                f"전환: {_state_display(item.previous_state)} → {_state_display(item.current_state)}",
                f"이전: {item.previous_label_date} · {item.previous_label}",
                f"현재: {item.current_label_date} · {item.current_label}",
                f"판정: {item.verdict}",
                f"행동: {item.action}",
            ]
        )
    if errors:
        lines.append("")
        lines.append("오류: " + " · ".join(symbol for symbol, _error in errors[:5]))
    return "\n".join(lines)


def _state_display(state_key: str) -> str:
    labels = {
        "ACTIVE_BUY": "활성 매수",
        "BLOCKED_BUY": "매수 차단",
        "CAUTION_BUY": "추격 주의",
        "SETUP": "셋업 관찰",
        "EXIT": "청산/이탈",
        "OBSERVE": "관찰",
        "IDLE": "신호 없음",
    }
    return labels.get(state_key, state_key)


def _state_changed(previous: sqlite3.Row, current: SymbolLazyAlphaState) -> bool:
    return (
        str(previous["state_key"]) != current.state_key
        or str(previous["label"]) != current.label
        or str(previous["label_date"]) != current.label_date
    )


def _state_from_outcome(
    outcome: TradingViewLabelOutcome,
    table: TradingViewTableSnapshot | None = None,
) -> SymbolLazyAlphaState:
    decision = evaluate_lazy_alpha_state(
        outcome_label=outcome.label,
        table_signal=table.signal if table else None,
        table_conviction=table.conviction if table else None,
        table_buy_eligibility=table.buy_eligibility if table else None,
        table_score=table.aux_score if table else None,
        penalty=outcome.score_penalty_hint,
        outcome=outcome,
    )
    state_key = _state_key_from_decision(decision.verdict)
    return SymbolLazyAlphaState(
        symbol=outcome.symbol,
        market=outcome.market,
        state_key=state_key,
        label=outcome.label,
        label_date=outcome.signal_date,
        verdict=decision.verdict,
        action=decision.action,
    )


def _state_key_from_decision(verdict: str) -> str:
    if verdict == "매수 금지":
        return "BLOCKED_BUY"
    if verdict == "추격 주의":
        return "CAUTION_BUY"
    return "ACTIVE_BUY"


def _state_from_exclusion(exclusion: TradingViewExcludedSignal) -> SymbolLazyAlphaState:
    decision = evaluate_lazy_alpha_state(exclusion_label=exclusion.exit_label)
    return SymbolLazyAlphaState(
        symbol=exclusion.symbol,
        market=exclusion.market,
        state_key="EXIT",
        label=exclusion.exit_label,
        label_date=exclusion.exit_date or "차트 우측 최신 라벨",
        verdict=decision.verdict,
        action=decision.action,
    )


def _state_from_flow(symbol: str, flows: list) -> SymbolLazyAlphaState:
    market = "KR" if symbol.startswith("KRX:") else "US" if ":" in symbol else "UNKNOWN"
    if flows:
        latest = sorted(flows, key=lambda item: item.bar_index)[-1]
        if "셋업" in latest.label:
            return SymbolLazyAlphaState(
                symbol=symbol,
                market=market,
                state_key="SETUP",
                label=latest.label,
                label_date=latest.date,
                verdict="셋업 관찰",
                action="진입 라벨 대기",
            )
        return SymbolLazyAlphaState(
            symbol=symbol,
            market=market,
            state_key="OBSERVE",
            label=latest.label,
            label_date=latest.date,
            verdict="관찰",
            action="진입/청산 라벨 확인",
        )
    return SymbolLazyAlphaState(
        symbol=symbol,
        market=market,
        state_key="IDLE",
        label="라벨 없음",
        label_date="-",
        verdict="관망",
        action="셋업 형성 또는 진입 라벨 대기",
    )


def _latest_exclusions_by_symbol(
    exclusions: list[TradingViewExcludedSignal],
) -> list[TradingViewExcludedSignal]:
    latest: dict[str, TradingViewExcludedSignal] = {}
    for item in exclusions:
        previous = latest.get(item.symbol)
        if previous is None or (item.exit_bar_index, item.entry_bar_index) > (
            previous.exit_bar_index,
            previous.entry_bar_index,
        ):
            latest[item.symbol] = item
    return list(latest.values())
