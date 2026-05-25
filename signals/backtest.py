"""Post-signal price outcome audit for Master Score calibration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from signals.master_score import build_master_scorecard_for_payload
from signals.market import ticker_for_lookup
from signals.storage import SignalEventRow

_KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class PricePoint:
    date: str
    close: float


class PriceHistoryProvider:
    def closes(self, *, ticker: str, market: str, start: str, end: str) -> list[PricePoint]:
        raise NotImplementedError


@dataclass(frozen=True)
class SignalOutcome:
    ticker: str
    market: str
    signal_date: str
    action: str
    master_score: int | None
    rating: str | None
    entry_price: float | None
    returns: dict[str, float | None]
    status: str
    warning: str | None = None


def audit_signal_outcomes(
    rows: list[SignalEventRow],
    *,
    price_provider: PriceHistoryProvider,
    horizons: tuple[int, ...] = (5, 10, 20),
) -> list[SignalOutcome]:
    outcomes: list[SignalOutcome] = []
    for row in rows:
        payload = _payload(row)
        signal_date = datetime.fromtimestamp(row.received_at, tz=_KST).date().isoformat()
        scorecard = build_master_scorecard_for_payload(
            payload,
            independence_status=row.independence_status,
        )
        start = signal_date
        end = (datetime.fromisoformat(signal_date) + timedelta(days=max(horizons) * 3 + 10)).date().isoformat()
        try:
            closes = price_provider.closes(
                ticker=ticker_for_lookup(row.ticker, row.market),
                market=row.market,
                start=start,
                end=end,
            )
        except Exception as exc:
            outcomes.append(
                SignalOutcome(
                    ticker=row.ticker,
                    market=row.market,
                    signal_date=signal_date,
                    action=row.action,
                    master_score=scorecard.total if scorecard else None,
                    rating=scorecard.rating if scorecard else None,
                    entry_price=_float_or_none(payload.get("price")),
                    returns={f"{h}d": None for h in horizons},
                    status="price_error",
                    warning=str(exc),
                )
            )
            continue

        entry = _entry_price(payload, closes)
        returns: dict[str, float | None] = {}
        for horizon in horizons:
            returns[f"{horizon}d"] = _horizon_return(entry, closes, horizon)

        status = "ok" if any(value is not None for value in returns.values()) else "insufficient_future"
        outcomes.append(
            SignalOutcome(
                ticker=row.ticker,
                market=row.market,
                signal_date=signal_date,
                action=row.action,
                master_score=scorecard.total if scorecard else None,
                rating=scorecard.rating if scorecard else None,
                entry_price=entry,
                returns=returns,
                status=status,
                warning=None if status == "ok" else "not enough future trading days",
            )
        )
    return outcomes


def format_outcome_report(outcomes: list[SignalOutcome]) -> str:
    lines = ["Master Score 사후검증", f"샘플: {len(outcomes)}건", ""]
    if not outcomes:
        lines.append("검증할 BUY 시그널이 없습니다.")
        return "\n".join(lines)

    lines.append("ticker | date | score | rating | 5d | 10d | 20d | status")
    lines.append("-" * 68)
    for item in outcomes:
        lines.append(
            " | ".join(
                [
                    item.ticker,
                    item.signal_date,
                    "-" if item.master_score is None else str(item.master_score),
                    item.rating or "-",
                    _fmt_pct(item.returns.get("5d")),
                    _fmt_pct(item.returns.get("10d")),
                    _fmt_pct(item.returns.get("20d")),
                    item.status,
                ]
            )
        )
    return "\n".join(lines)


def _payload(row: SignalEventRow) -> dict:
    try:
        return json.loads(row.payload_json)
    except json.JSONDecodeError:
        return {}


def _entry_price(payload: dict, closes: list[PricePoint]) -> float | None:
    return _float_or_none(payload.get("price")) or (closes[0].close if closes else None)


def _horizon_return(entry: float | None, closes: list[PricePoint], horizon: int) -> float | None:
    if entry is None or entry == 0 or len(closes) <= horizon:
        return None
    return round((closes[horizon].close / entry - 1) * 100, 2)


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"

