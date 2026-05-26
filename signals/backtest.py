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
_BUCKET_ORDER = ("90+", "80-89", "70-79", "<70")


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
    independence_status: str | None = None
    warning: str | None = None


@dataclass(frozen=True)
class OutcomeBucketSummary:
    count: int
    avg_5d: float | None
    avg_10d: float | None
    avg_20d: float | None
    win_rate_20d: int


@dataclass(frozen=True)
class OutcomeCalibrationSummary:
    sample_count: int
    valid_count: int
    buckets: dict[str, OutcomeBucketSummary]
    failure_modes: dict[str, int]
    status_counts: dict[str, int]
    independence_status_counts: dict[str, int]


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
                ticker=_ticker_for_price_provider(row),
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
                    independence_status=row.independence_status,
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
                independence_status=row.independence_status,
                warning=None if status == "ok" else "not enough future trading days",
            )
        )
    return outcomes


def summarize_outcomes(outcomes: list[SignalOutcome]) -> OutcomeCalibrationSummary:
    status_counts: dict[str, int] = {}
    bucket_items: dict[str, list[SignalOutcome]] = {bucket: [] for bucket in _BUCKET_ORDER}
    failure_modes: dict[str, int] = {}
    independence_status_counts: dict[str, int] = {}

    for outcome in outcomes:
        status_counts[outcome.status] = status_counts.get(outcome.status, 0) + 1
        if outcome.independence_status:
            independence_status_counts[outcome.independence_status] = (
                independence_status_counts.get(outcome.independence_status, 0) + 1
            )
        if outcome.status != "ok":
            continue
        bucket_items[_score_bucket(outcome.master_score)].append(outcome)
        failure = _failure_mode(outcome)
        if failure:
            failure_modes[failure] = failure_modes.get(failure, 0) + 1

    buckets = {
        bucket: _summarize_bucket(items)
        for bucket, items in bucket_items.items()
        if items
    }
    return OutcomeCalibrationSummary(
        sample_count=len(outcomes),
        valid_count=sum(1 for item in outcomes if item.status == "ok"),
        buckets=buckets,
        failure_modes=failure_modes,
        status_counts=status_counts,
        independence_status_counts=independence_status_counts,
    )


def format_calibration_report(outcomes: list[SignalOutcome]) -> str:
    summary = summarize_outcomes(outcomes)
    lines = [
        "🧪 Master Score 사후검증",
        f"샘플: {summary.sample_count}건 · 유효: {summary.valid_count}건",
        "",
    ]
    if not outcomes:
        lines.append("검증할 BUY 시그널이 없습니다.")
        return "\n".join(lines)
    if summary.valid_count == 0:
        lines.append("아직 유효한 미래 가격 데이터가 없습니다.")
    else:
        lines.append("점수대별 20거래일 성과")
        for bucket in _BUCKET_ORDER:
            item = summary.buckets.get(bucket)
            if not item:
                continue
            lines.append(
                f"{bucket}: {item.count}건 · 20d 승률 {item.win_rate_20d}% · 평균 {_fmt_pct(item.avg_20d)}"
            )

    if summary.failure_modes:
        lines.append("")
        lines.append("실패유형: " + " · ".join(
            f"{name} {count}건" for name, count in summary.failure_modes.items()
        ))

    independence_line = _format_independence_status_counts(summary.independence_status_counts)
    if independence_line:
        lines.append("")
        lines.append("독립성표본: " + independence_line)
        lines.append("해석: 차단/보류 신호는 수익률과 별개로 매입 후보에서 제외 또는 원천 확인 대상입니다.")

    non_ok = {
        status: count
        for status, count in summary.status_counts.items()
        if status != "ok"
    }
    if non_ok:
        lines.append("")
        lines.append("데이터상태: " + " · ".join(
            f"{status} {count}건" for status, count in non_ok.items()
        ))
    return "\n".join(lines)


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


def _ticker_for_price_provider(row: SignalEventRow) -> str:
    if ":" in row.ticker:
        return row.ticker
    exchange = (row.exchange or "").strip().upper()
    if exchange:
        return f"{exchange}:{row.ticker}"
    return ticker_for_lookup(row.ticker, row.market)


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


def _score_bucket(score: int | None) -> str:
    if score is None:
        return "<70"
    if score >= 90:
        return "90+"
    if score >= 80:
        return "80-89"
    if score >= 70:
        return "70-79"
    return "<70"


def _summarize_bucket(outcomes: list[SignalOutcome]) -> OutcomeBucketSummary:
    returns_5d = [item.returns.get("5d") for item in outcomes]
    returns_10d = [item.returns.get("10d") for item in outcomes]
    returns_20d = [item.returns.get("20d") for item in outcomes]
    valid_20d = [value for value in returns_20d if value is not None]
    win_rate_20d = 0
    if valid_20d:
        win_rate_20d = round(sum(1 for value in valid_20d if value > 0) / len(valid_20d) * 100)
    return OutcomeBucketSummary(
        count=len(outcomes),
        avg_5d=_avg(returns_5d),
        avg_10d=_avg(returns_10d),
        avg_20d=_avg(returns_20d),
        win_rate_20d=win_rate_20d,
    )


def _avg(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 2)


def _failure_mode(outcome: SignalOutcome) -> str | None:
    return_5d = outcome.returns.get("5d")
    return_10d = outcome.returns.get("10d")
    return_20d = outcome.returns.get("20d")
    if return_20d is None or return_20d > -5:
        return None
    if return_5d is not None and return_5d <= -7:
        return "외생/갭하락 의심 또는 즉시 실패"
    if (
        return_5d is not None
        and return_10d is not None
        and return_5d < 0
        and return_10d < 0
    ):
        return "페이크/휩쏘 돌파"
    return "미분류: 뉴스/섹터/실적 확인 필요"


def _format_independence_status_counts(counts: dict[str, int]) -> str | None:
    watched = {
        "BLOCKED_CONFIRMED": "차단 확정",
        "BLOCKED_POSSIBLE": "차단 가능",
        "MANUAL_VERIFY": "원천 확인 필요",
        "MANUAL_VERIFY_CURRENT_YEAR": "현재연도 확인 필요",
        "DATA_MISSING": "감사인 데이터 없음",
        "UNKNOWN_MARKET": "시장 확인 필요",
        "ROLLOVER_INFERRED": "감사인 추정",
    }
    parts = [
        f"{label} {counts[status]}건"
        for status, label in watched.items()
        if counts.get(status)
    ]
    return " · ".join(parts) if parts else None
