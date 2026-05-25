"""Telegram console view for stored Lazy Alpha signal events."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from signals.master_score import build_master_scorecard_for_payload, format_master_score_for_payload
from signals.storage import ActiveSignalRow, SignalEventRow


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
    view: str = "ACTIVE"
    tab: str = "BUY"
    market: str = "ALL"
    hours: int = 8
    sort: str = "TIME"


def parse_console_args(args: list[str]) -> ConsoleState:
    view = "ACTIVE"
    tab = "BUY"
    market = "ALL"
    hours = 8
    sort = "TIME"
    for raw in args:
        value = raw.lower()
        if value in {"active", "현재", "활성"}:
            view = "ACTIVE"
        elif value in {"recent", "event", "events", "최근"}:
            view = "RECENT"
        elif value in {"buy", "매수"}:
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
        elif value in {"score", "scores", "점수", "점수순", "rank", "ranking"}:
            sort = "SCORE"
        elif value in {"time", "recent", "시간", "최신"}:
            sort = "TIME"
        elif value.endswith("h") and value[:-1].isdigit():
            hours = max(1, min(int(value[:-1]), 72))
    return ConsoleState(view=view, tab=tab, market=market, hours=hours, sort=sort)


def parse_console_callback(data: str) -> ConsoleState:
    if data.startswith("sig:"):
        data = data.removeprefix("sig:")
    parts = dict(part.split("=", 1) for part in data.split(";") if "=" in part)
    return ConsoleState(
        view=parts.get("view", "ACTIVE"),
        tab=parts.get("tab", "BUY"),
        market=parts.get("market", "ALL"),
        hours=int(parts.get("hours", "8")),
        sort=parts.get("sort", "TIME"),
    )


def format_console(
    *,
    rows: list[SignalEventRow] | list[ActiveSignalRow],
    state: ConsoleState,
    now: int | None = None,
    limit: int = 12,
) -> str:
    current = int(now if now is not None else time.time())
    since = current - state.hours * 3600
    filtered = [
        row
        for row in rows
        if _row_timestamp(row) >= since
        and _matches_tab(row, state.tab)
        and (state.market == "ALL" or row.market == state.market)
    ]
    if state.sort == "SCORE":
        filtered = sorted(filtered, key=_sort_score, reverse=True)
    filtered = filtered[:limit]

    lines = [
        "📡 Lazy Alpha Signal Console",
        f"보기: {_view_label(state.view)} · 기준: 최근 {state.hours}시간 · 탭: {TAB_LABELS.get(state.tab, state.tab)} · 시장: {MARKET_LABELS.get(state.market, state.market)} · 정렬: {_sort_label(state.sort)}",
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
        active_age = _active_age(row, current)
        active_suffix = f" · active {active_age}" if active_age else ""
        master_score = _master_score_text(row)
        master_score_line = f"\n   {master_score.splitlines()[0]}" if master_score else ""
        lines.append(
            f"{idx}. {name} ({row.ticker}) · {row.market} · {row.action}\n"
            f"   {row.base_type} · Score {score} · {conviction}등급 · 독립성 {row.independence_status}{active_suffix}"
            f"{master_score_line}"
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
    master_score = format_master_score_for_payload(
        payload,
        independence_status=row.independence_status,
    )
    master_score_lines = [master_score, ""] if master_score else []
    return "\n".join(
        [
            f"🔎 {name} ({row.ticker})",
            f"시그널: {row.action} · {row.base_type} · {row.timeframe}",
            f"판단: {status} · Score {score} · {conviction}등급",
            *master_score_lines,
            f"일봉: {daily_trend} · RS {daily_rs}",
            f"과열/리스크: sb_z_score {z_score} · ATR dot {atr_dot}",
            f"독립성: {row.independence_status}",
        ]
    )


def build_console_keyboard(state: ConsoleState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _button("현재 활성", state, view="ACTIVE"),
                _button("최근 발생", state, view="RECENT"),
            ],
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
            [
                _button("최신순", state, sort="TIME"),
                _button("점수순", state, sort="SCORE"),
            ],
        ]
    )


def _button(
    label: str,
    state: ConsoleState,
    *,
    view: str | None = None,
    tab: str | None = None,
    market: str | None = None,
    hours: int | None = None,
    sort: str | None = None,
) -> InlineKeyboardButton:
    next_state = ConsoleState(
        view=view or state.view,
        tab=tab or state.tab,
        market=market or state.market,
        hours=hours or state.hours,
        sort=sort or state.sort,
    )
    return InlineKeyboardButton(label, callback_data=_callback_data(next_state))


def _callback_data(state: ConsoleState) -> str:
    return f"sig:view={state.view};tab={state.tab};market={state.market};hours={state.hours};sort={state.sort}"


def _matches_tab(row: SignalEventRow | ActiveSignalRow, tab: str) -> bool:
    if tab == "BUY":
        if isinstance(row, ActiveSignalRow):
            return row.action == "BUY"
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


def _sort_score(row: SignalEventRow | ActiveSignalRow) -> float:
    payload = _payload(row)
    scorecard = build_master_scorecard_for_payload(
        payload,
        independence_status=row.independence_status,
    )
    if scorecard is not None:
        return float(scorecard.total)
    return _float_or_zero(payload.get("score"))


def _master_score_text(row: SignalEventRow | ActiveSignalRow) -> str | None:
    return format_master_score_for_payload(
        _payload(row),
        independence_status=row.independence_status,
    )


def _float_or_zero(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _row_timestamp(row: SignalEventRow | ActiveSignalRow) -> int:
    return row.received_at if isinstance(row, SignalEventRow) else row.updated_at


def _active_age(row: SignalEventRow | ActiveSignalRow, now: int) -> str:
    if not isinstance(row, ActiveSignalRow):
        return ""
    minutes = max(0, (now - row.activated_at) // 60)
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h {minutes % 60}m"


def _view_label(view: str) -> str:
    return "현재 활성" if view == "ACTIVE" else "최근 발생"


def _sort_label(sort: str) -> str:
    return "점수순" if sort == "SCORE" else "최신순"
