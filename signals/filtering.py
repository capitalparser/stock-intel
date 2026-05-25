"""Buy-signal and signal-quality filters."""

from __future__ import annotations

from dataclasses import dataclass

from signals.payload import TradingViewSignal

BUY_BASE_TYPES = {
    "💰 정석 진입",
    "🚀 돌파 진입",
    "⚡ 공격 진입",
    "🔼 피라미딩 추매",
    "📈 모멘텀 BUY",
    "PEG Pullback",
    "PEG Rebreak",
}


@dataclass(frozen=True)
class FilterDecision:
    allowed: bool
    status: str
    reason: str


def decide_signal_filter(signal: TradingViewSignal) -> FilterDecision:
    if signal.action != "BUY":
        return FilterDecision(False, "FILTERED", f"action={signal.action} (not BUY)")
    if signal.base_type() not in BUY_BASE_TYPES:
        return FilterDecision(False, "FILTERED", f"type={signal.base_type()} not allowed")
    if signal.conviction == "D":
        return FilterDecision(False, "FILTERED", "conviction=D")
    if signal.ema_align == "역배열":
        return FilterDecision(False, "FILTERED", "ema_align=역배열")
    return FilterDecision(True, "ALLOWED", "")

