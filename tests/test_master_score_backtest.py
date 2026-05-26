from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from signals.backtest import (
    PriceHistoryProvider,
    PricePoint,
    audit_signal_outcomes,
    format_calibration_report,
    format_outcome_report,
    summarize_outcomes,
)
from signals.storage import SignalEventRow

FIXTURES = Path(__file__).parent / "fixtures"


class FakePriceHistoryProvider(PriceHistoryProvider):
    def __init__(self, closes: list[PricePoint]) -> None:
        self.closes_result = closes
        self.calls: list[dict] = []

    def closes(self, *, ticker: str, market: str, start: str, end: str) -> list[PricePoint]:
        self.calls.append({"ticker": ticker, "market": market, "start": start, "end": end})
        return self.closes_result


def test_audit_signal_outcomes_scores_event_and_calculates_forward_returns():
    row = _event_row(
        payload=json.loads((FIXTURES / "tradingview_v6_2_buy_aapl.json").read_text()),
        received_at=_ts("2026-01-02T10:00:00+09:00"),
    )
    provider = FakePriceHistoryProvider(
        [
            PricePoint(date=f"2026-01-{day:02d}", close=100 + day)
            for day in range(2, 24)
        ]
    )

    outcomes = audit_signal_outcomes([row], price_provider=provider, horizons=(5, 10, 20))

    assert provider.calls[0]["ticker"] == "NASDAQ:AAPL"
    assert provider.calls[0]["market"] == "US"
    assert provider.calls[0]["start"] == "2026-01-02"
    assert outcomes[0].master_score is not None
    assert outcomes[0].rating is not None
    assert outcomes[0].status == "ok"
    assert outcomes[0].entry_price == 195.5
    assert outcomes[0].returns == {
        "5d": -45.27,
        "10d": -42.71,
        "20d": -37.6,
    }


def test_audit_signal_outcomes_marks_insufficient_future_data():
    row = _event_row(
        payload=json.loads((FIXTURES / "tradingview_v6_2_buy_aapl.json").read_text()),
        received_at=_ts("2026-01-02T10:00:00+09:00"),
    )
    provider = FakePriceHistoryProvider([PricePoint(date="2026-01-02", close=195.5)])

    outcomes = audit_signal_outcomes([row], price_provider=provider, horizons=(5,))

    assert outcomes[0].status == "insufficient_future"
    assert outcomes[0].returns == {"5d": None}
    assert outcomes[0].warning == "not enough future trading days"


def test_format_outcome_report_handles_empty_sample():
    text = format_outcome_report([])

    assert "샘플: 0건" in text
    assert "검증할 BUY 시그널이 없습니다." in text


def test_summarize_outcomes_groups_score_buckets_and_failure_modes():
    outcomes = [
        _outcome(score=92, returns={"5d": 4.0, "10d": 8.0, "20d": 12.0}),
        _outcome(score=86, returns={"5d": -3.0, "10d": -8.0, "20d": -12.0}),
        _outcome(score=64, returns={"5d": -1.0, "10d": 2.0, "20d": 4.0}),
        _outcome(score=None, returns={"5d": None, "10d": None, "20d": None}, status="price_error"),
    ]

    summary = summarize_outcomes(outcomes)

    assert summary.sample_count == 4
    assert summary.valid_count == 3
    assert summary.buckets["90+"].count == 1
    assert summary.buckets["80-89"].win_rate_20d == 0
    assert summary.buckets["80-89"].avg_20d == -12.0
    assert summary.failure_modes["페이크/휩쏘 돌파"] == 1
    assert summary.status_counts["price_error"] == 1


def test_format_calibration_report_is_telegram_card_style():
    outcomes = [
        _outcome(score=92, rating="LEADER", returns={"5d": 4.0, "10d": 8.0, "20d": 12.0}),
        _outcome(score=86, rating="ENTRY", returns={"5d": -3.0, "10d": -8.0, "20d": -12.0}),
        _outcome(score=64, rating="WATCH", returns={"5d": -1.0, "10d": 2.0, "20d": 4.0}),
    ]

    text = format_calibration_report(outcomes)

    assert "🧪 Master Score 사후검증" in text
    assert "샘플: 3건 · 유효: 3건" in text
    assert "90+: 1건 · 20d 승률 100% · 평균 +12.00%" in text
    assert "80-89: 1건 · 20d 승률 0% · 평균 -12.00%" in text
    assert "실패유형: 페이크/휩쏘 돌파 1건" in text
    assert "ticker |" not in text


def _event_row(*, payload: dict, received_at: int) -> SignalEventRow:
    return SignalEventRow(
        ticker=payload["ticker"],
        exchange=payload["exchange"],
        market="US",
        timeframe=payload["timeframe"],
        action=payload["action"],
        base_type=payload["type"].removesuffix(" @SR↩").strip(),
        independence_status="CLEAR",
        filter_status="ALLOWED",
        payload_json=json.dumps(payload),
        telegram_sent=True,
        received_at=received_at,
    )


def _ts(value: str) -> int:
    return int(datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Seoul")).timestamp())


def _outcome(
    *,
    score: int | None,
    returns: dict[str, float | None],
    rating: str | None = "ENTRY",
    status: str = "ok",
) -> SignalOutcome:
    from signals.backtest import SignalOutcome

    return SignalOutcome(
        ticker="KRX:000000",
        market="KR",
        signal_date="2026-01-02",
        action="BUY",
        master_score=score,
        rating=rating,
        entry_price=100.0,
        returns=returns,
        status=status,
    )
