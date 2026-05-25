"""Telegram console view for stored Lazy Alpha signal events."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from signals.storage import SignalEventRow


TAB_LABELS = {
    "BUY": "매수",
    "SELL": "매도",
    "REVIEW": "확인필요",
    "ALL": "전체",
}
MARKET_LABELS = {
    "ALL": "전체",
    "KR": "국장",
    "US": "미국",
    "JP": "일본",
}


@dataclass(frozen=True)
class ConsoleState:
    tab: str = "BUY"
    market: str = "ALL"
    hours: int = 8


def parse_console_args(args: list[str]) -> ConsoleState:
    tab = "BUY"
    market = "ALL"
    hours = 8
    for raw in args:
        value = raw.lower()
        if value in {"buy", "매수"}:
            tab = "BUY"
        elif value in {"sell", "매도"}:
            tab = "SELL"
        elif value in {"review", "manual", "확인필요"}:
            tab = "REVIEW"
        elif value in {"kr", "국장"}:
            market = "KR"
        elif value in {"us", "미국"}:
            market = "US"
        elif value in {"jp", "일본"}:
            market = "JP"
        elif value.endswith("h") and value[:-1].isdigit():
            hours = max(1, min(int(value[:-1]), 72))
    return ConsoleState(tab=tab, market=market, hours=hours)


def parse_console_callback(data: str) -> ConsoleState:
    if data.startswith("sig:"):
        data = data.removeprefix("sig:")
    parts = dict(part.split("=", 1) for part in data.split(";") if "=" in part)
    return ConsoleState(
        tab=parts.get("tab", "BUY"),
        market=parts.get("market", "ALL"),
        hours=int(parts.get("hours", "8")),
    )


def format_console(
    *,
    rows: list[SignalEventRow],
    state: ConsoleState,
    now: int | None = None,
    limit: int = 12,
) -> str:
    current = int(now if now is not None else time.time())
    since = current - state.hours * 3600
    filtered = [
        row
        for row in rows
        if row.received_at >= since
        and _matches_tab(row, state.tab)
        and (state.market == "ALL" or row.market == state.market)
    ][:limit]

    lines = [
        "📡 Lazy Alpha Signal Console",
        f"기준: 최근 {state.hours}시간 · 탭: {TAB_LABELS.get(state.tab, state.tab)} · 시장: {MARKET_LABELS.get(state.market, state.market)}",
        "",
    ]
    if not filtered:
        lines.append("표시할 시그널이 없습니다.")
        return "\n".join(lines)

    for idx, row in enumerate(filtered, start=1):
        payload = _payload(row)
        name = payload.get("name") or row.ticker
        score = payload.get("score", "-")
        conviction = payload.get("conviction", "-")
        lines.append(
            f"{idx}. {name} ({row.ticker}) · {row.market} · {row.action}\n"
            f"   {row.base_type} · Score {score} · {conviction}등급 · 독립성 {row.independence_status}"
        )
    return "\n".join(lines)


def format_signal_detail(row: SignalEventRow | None, *, now: int | None = None) -> str:
    if row is None:
        return "해당 종목의 저장된 Lazy Alpha 시그널이 없습니다."
    payload = _payload(row)
    name = payload.get("name") or row.ticker
    score = payload.get("score", "-")
    conviction = payload.get("conviction", "-")
    status = payload.get("status") or "-"
    z_score = payload.get("sb_z_score", "-")
    atr_dot = payload.get("atr_dot", "-")
    daily_trend = payload.get("daily_trend") or "-"
    daily_rs = payload.get("daily_rs", "-")
    return "\n".join(
        [
            f"🔎 {name} ({row.ticker})",
            f"시그널: {row.action} · {row.base_type} · {row.timeframe}",
            f"판단: {status} · Score {score} · {conviction}등급",
            f"일봉: {daily_trend} · RS {daily_rs}",
            f"과열/리스크: sb_z_score {z_score} · ATR dot {atr_dot}",
            f"독립성: {row.independence_status}",
        ]
    )


def build_console_keyboard(state: ConsoleState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _button("매수", state, tab="BUY"),
                _button("매도", state, tab="SELL"),
                _button("확인필요", state, tab="REVIEW"),
            ],
            [
                _button("전체", state, market="ALL"),
                _button("국장", state, market="KR"),
                _button("미국", state, market="US"),
                _button("일본", state, market="JP"),
            ],
            [
                _button("4h", state, hours=4),
                _button("8h", state, hours=8),
                _button("24h", state, hours=24),
                _button("새로고침", state),
            ],
        ]
    )


def _button(
    label: str,
    state: ConsoleState,
    *,
    tab: str | None = None,
    market: str | None = None,
    hours: int | None = None,
) -> InlineKeyboardButton:
    next_state = ConsoleState(
        tab=tab or state.tab,
        market=market or state.market,
        hours=hours or state.hours,
    )
    return InlineKeyboardButton(label, callback_data=_callback_data(next_state))


def _callback_data(state: ConsoleState) -> str:
    return f"sig:tab={state.tab};market={state.market};hours={state.hours}"


def _matches_tab(row: SignalEventRow, tab: str) -> bool:
    if tab == "BUY":
        return row.action == "BUY" and row.filter_status == "ALLOWED"
    if tab == "SELL":
        return row.action == "SELL"
    if tab == "REVIEW":
        return row.independence_status in {"MANUAL_VERIFY", "BLOCKED", "UNKNOWN_MARKET"}
    return True


def _payload(row: SignalEventRow) -> dict:
    try:
        return json.loads(row.payload_json)
    except json.JSONDecodeError:
        return {}
