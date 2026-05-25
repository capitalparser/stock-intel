"""Telegram formatting for TradingView signal alerts."""

from __future__ import annotations

from signals.filtering import FilterDecision
from signals.independence import IndependenceDecision
from signals.market import Market
from signals.payload import TradingViewSignal


def format_signal_alert(
    signal: TradingViewSignal,
    market: Market,
    filter_decision: FilterDecision,
    independence_decision: IndependenceDecision,
    audit_firm: dict | None = None,
) -> str:
    first = _status_line(independence_decision.status)
    price = f"{signal.price:,.2f}" if market.code != "KR" else f"{signal.price:,.0f}원"
    sl = "-" if signal.sl is None else (f"{signal.sl:,.2f}" if market.code != "KR" else f"{signal.sl:,.0f}원")
    rr = "-" if signal.rr is None else f"{signal.rr:.1f}"
    heat = _heat_line(signal)
    auditor = independence_decision.auditor or "-"
    lines = [
        first,
        f"종목: {signal.name} ({signal.exchange}:{signal.ticker}) · {market.label}",
        f"시그널: {signal.type} · {signal.timeframe}",
        f"가격: {price} | 손절: {sl} | RR: {rr}",
        f"품질: {signal.conviction}등급 · Score {signal.score} · {signal.status}",
        f"일봉: {signal.daily_trend} · RS {signal.daily_rs} · 200MA 위={signal.daily_above_200ma}",
        heat,
        f"감사인: {auditor}",
        f"판정: {independence_decision.reason}",
        f"trace: TradingView webhook {signal.schema_version}",
    ]
    if not filter_decision.allowed:
        lines.insert(1, f"필터: {filter_decision.reason}")
    return "\n".join(lines)


def _status_line(status: str) -> str:
    if status == "BLOCKED_CONFIRMED":
        return "🚫 독립성 차단 — 매입 검토 금지"
    if status == "BLOCKED_POSSIBLE":
        return "🚫 독립성 차단 가능 — 원천 확인 전 매입 보류"
    if status == "CLEAR_CONFIRMED":
        return "🟢 매수 시그널 — 독립성 차단 없음"
    if status == "ROLLOVER_INFERRED":
        return "🟡 감사인 추정 — 원천 확인 전 매입 보류"
    return "🟡 독립성 확인 필요 — 원천 확인 전 매입 보류"


def _heat_line(signal: TradingViewSignal) -> str:
    warnings: list[str] = []
    if signal.atr_dot:
        warnings.append("ATR 과열봉")
    if signal.sb_z_score > 2.5:
        warnings.append("시그마 과열")
    if warnings:
        return "과열: " + ", ".join(warnings)
    return f"과열: 특이 없음 (z={signal.sb_z_score:.2f})"
