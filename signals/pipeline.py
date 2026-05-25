"""TradingView signal alert orchestration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from signals.filtering import decide_signal_filter
from signals.formatting import format_signal_alert
from signals.independence import decide_independence
from signals.market import classify_market
from signals.payload import TradingViewSignal
from signals.storage import SignalStore

AuditLookup = Callable[[str], dict]
SendMessage = Callable[[str], Awaitable[bool]]


@dataclass(frozen=True)
class PipelineResult:
    ticker: str
    filter_status: str
    independence_status: str
    telegram_sent: bool


class SignalPipeline:
    def __init__(
        self,
        *,
        store: SignalStore,
        audit_lookup: AuditLookup,
        send_message: SendMessage,
    ) -> None:
        self._store = store
        self._audit_lookup = audit_lookup
        self._send_message = send_message

    async def handle_payload(self, payload: dict) -> PipelineResult:
        signal = TradingViewSignal.model_validate(payload)
        market = classify_market(signal.ticker, signal.exchange)
        filter_decision = decide_signal_filter(signal)

        audit = self._audit_lookup(signal.ticker) if market.code == "KR" else {}
        independence = decide_independence(market, audit)

        telegram_sent = False
        if filter_decision.allowed:
            text = format_signal_alert(signal, market, filter_decision, independence, audit)
            telegram_sent = await self._send_message(text)

        self._store.put_event(
            signal=signal,
            market=market.code,
            independence_status=independence.status,
            filter_status=filter_decision.status,
            telegram_sent=telegram_sent,
        )
        return PipelineResult(
            ticker=signal.ticker,
            filter_status=filter_decision.status,
            independence_status=independence.status,
            telegram_sent=telegram_sent,
        )
