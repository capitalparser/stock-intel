import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from signals.backtest import (
    PriceHistoryProvider,
    PricePoint,
    audit_signal_outcomes,
    format_outcome_report,
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

    assert provider.calls[0]["ticker"] == "AAPL"
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
