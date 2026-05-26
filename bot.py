"""bot.py — 04_stock_intel Telegram 봇 진입점.

종목명 입력 → search_ticker → 4개 data 모듈 조회 → 포맷 → 전송.
data/ 모듈은 모두 동기 함수 → asyncio.to_thread()로 래핑.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# DB_URL 환경변수 로드 순서: load_dotenv() 먼저, 그 다음 kreports import
load_dotenv()

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from data.audit_firm import fetch_audit_firm
from data.fundamental import fetch_fundamental
from data.short_sell import fetch_short_sell
from data.supply import fetch_supply
from data.technical import fetch_technical
from signals.console import (
    build_console_keyboard,
    format_console,
    format_signal_detail,
    parse_console_args,
    parse_console_callback,
)
from signals.backtest import (
    PriceHistoryProvider,
    PricePoint,
    audit_signal_outcomes,
    format_calibration_report,
)
from signals.independence import format_independence_alert, decide_independence
from signals.kr_watch_candidates import KR_CANDIDATE_SEEDS
from signals.lazy_alpha_transitions import (
    LazyAlphaTransitionStore,
    build_symbol_states_from_scan,
    format_transition_report,
)
from signals.leading_discovery import (
    LeadingCandidate,
    format_leading_report,
    score_leading_candidate,
)
from signals.market import Market
from signals.price_history import (
    CachedPriceHistoryProvider,
    MarketPriceHistoryProvider,
    TradingViewPriceHistoryProvider,
)
from signals.tradingview_direct import TradingViewTableSnapshot, evaluate_lazy_alpha_state, interpret_lazy_alpha_flow
from signals.storage import SignalStore
from signals.telegram import send_telegram_message
from signals.tradingview_scan_runner import (
    TradingViewScanResult,
    adjusted_priority_penalty,
    build_signal_enrichments,
    format_scan_report,
    format_recommendation_report,
    normalize_scan_symbol,
    priority_sort_key,
    recommend_signal_candidates,
    scan_tradingview_symbols,
    symbols_from_universe,
)
from signals.tradingview_scan_cache import TradingViewScanCache
from signals.universe import (
    format_universe_summary,
    load_universe_snapshot,
    symbol_in_universe,
    sync_universe_from_tradingview,
)
from utils.formatter import format_message
from utils.ticker import load_ticker_cache, refresh_ticker_cache, search_ticker

# ---------------------------------------------------------------------------
# 로거
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 환경변수
# ---------------------------------------------------------------------------
TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

ALLOWED_IDS: set[int] = {
    int(x.strip())
    for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",")
    if x.strip()
}

# 02_audit_safe_signals feed 연동 (설정 안 하면 /feed 비활성)
_SIGNALS_URL: str = os.getenv("ASS_SIGNALS_URL", "")   # e.g. https://audit-safe-signals.fly.dev/signals
_SIGNALS_SECRET: str = os.getenv("ASS_SIGNALS_SECRET", "")
_KST = ZoneInfo("Asia/Seoul")

HELP_TEXT = (
    "종목명을 입력하면 수급현황, 공매도, 기술적 지표, 펀더멘탈, 감사법인을 보여드립니다.\n"
    "DM: 삼성전자 / SK하이닉스 / NAVER\n"
    "그룹: /종목 삼성전자 또는 /s 삼성전자\n\n"
    "/신호 — Lazy Alpha 버튼 콘솔\n"
    "/선행 kr — 수급+기술 전조 기반 국장 선행 후보\n"
    "/진입 — 현재 진입/매수 후보만 점수순 스캔\n"
    "/추천 kr 50 — 시세 반영 전 우선 검토 후보\n"
    "/추천쿨다운 — 추천 스캔 오류 심볼 쿨다운 조회\n"
    "/변화 — 이전 스캔 대비 Lazy Alpha 상태 전환만 확인\n"
    "/검증 kr 100 — 저장된 BUY 웹훅 시그널 사후검증\n"
    "/스캔 — TradingView 차트 직접 스캔(웹훅 미수신분 확인)\n"
    "/국장스캔 — TradingView 국장 watchlist 기술점수 스캔\n"
    "/스캔 us 5 — 관심 universe 중 미국 5종목 직접 스캔\n"
    "/신호 kr 8h — 최근 국장 매수 후보\n"
    "/종목 005930 — 특정 종목 Lazy Alpha 판단\n"
    "/조회 삼성전자 — 종목 리서치\n"
    "/universe — TradingView watchlist universe 요약\n"
    "/sync_universe — TradingView watchlist universe 동기화\n"
    "/feed — 최근 BUY 시그널 목록\n"
    "/feed 50 — 최근 50건"
)
_HELP_TEXT_SHORTCUTS = {"기능", "도움말", "메뉴", "help"}
_SIGNAL_CONSOLE_TEXT_SHORTCUTS = {"시그널", "신호", "signals", "signal"}
_TRADINGVIEW_SCAN_TEXT_SHORTCUTS = {"스캔", "현재신호", "국장스캔", "tvscan", "scan", "krscan"}
_LAZY_ALPHA_TRANSITION_TEXT_SHORTCUTS = {"변화", "상태변화", "전환", "알림", "changes", "transition", "transitions"}
_LEADING_DISCOVERY_TEXT_SHORTCUTS = {"선행", "발굴", "leading", "discover", "discovery"}
_BACKTEST_TEXT_SHORTCUTS = {"검증", "백테스트", "backtest", "audit"}
_RECOMMENDATION_TEXT_SHORTCUTS = {"추천", "후보", "추천후보", "recommend", "recommendations", "pick", "picks"}
_RECOMMENDATION_COOLDOWN_TEXT_SHORTCUTS = {"추천쿨다운", "쿨다운", "recommendcooldown", "cooldown"}

# ---------------------------------------------------------------------------
# 스케줄러
# ---------------------------------------------------------------------------
_KST = pytz.timezone("Asia/Seoul")
scheduler = AsyncIOScheduler(timezone=_KST)
async def _scheduled_cache_refresh() -> None:
    await asyncio.to_thread(refresh_ticker_cache)


scheduler.add_job(
    _scheduled_cache_refresh,
    CronTrigger(hour=7, minute=0, timezone=_KST),
    id="refresh_ticker_cache",
    replace_existing=True,
)


async def _scheduled_lazy_alpha_transition_alert() -> None:
    args = os.getenv("LAZY_ALPHA_TRANSITION_ALERT_ARGS", "전체 kr 80").split()
    text = await asyncio.to_thread(render_lazy_alpha_transition_report, args)
    if "새로 알릴 상태 전환이 없습니다." in text:
        logger.info("Lazy Alpha 상태 전환 없음")
        return
    await send_telegram_message(TOKEN, sorted(ALLOWED_IDS), text)


# ---------------------------------------------------------------------------
# 화이트리스트 체크
# ---------------------------------------------------------------------------
async def check_allowed(update: Update) -> bool:
    """ALLOWED_IDS 미설정 시 모두 허용 (개발 편의)."""
    if not ALLOWED_IDS:
        return True
    chat_id = update.effective_chat.id
    allowed = chat_id in ALLOWED_IDS
    if not allowed:
        logger.warning("차단된 chat_id: %s (허용 목록: %s)", chat_id, ALLOWED_IDS)
    return allowed


# ---------------------------------------------------------------------------
# 동기 fetch 래퍼 (asyncio.to_thread에서 실행)
# ---------------------------------------------------------------------------
def fetch_all(ticker: str) -> tuple[dict, dict, dict, dict, dict]:
    """5개 data 모듈 직렬 호출. asyncio.to_thread에서 실행."""
    supply = fetch_supply(ticker)
    short_sell = fetch_short_sell(ticker)
    technical = fetch_technical(ticker)
    fundamental = fetch_fundamental(ticker)
    audit = fetch_audit_firm(ticker)
    return supply, short_sell, technical, fundamental, audit


def render_stock_lookup_report(
    ticker: str,
    name: str,
    *,
    include_lazy_alpha: bool | None = None,
) -> str:
    supply, short_sell, technical, fundamental, audit = fetch_all(ticker)
    text = format_message(
        name,
        ticker,
        supply,
        short_sell,
        technical,
        fundamental,
        audit,
    )
    if ticker.isdigit() and len(ticker) == 6:
        decision = decide_independence(Market("KR", "한국"), audit)
        text = format_independence_alert(decision) + "\n" + text
    enabled = include_lazy_alpha
    if enabled is None:
        enabled = os.getenv("STOCK_LOOKUP_LAZY_ALPHA", "1") not in {"0", "false", "False"}
    if not enabled:
        return text
    return text + "\n\n" + render_lazy_alpha_status_for_symbol(f"KRX:{ticker}")


def render_lazy_alpha_status_for_symbol(symbol: str) -> str:
    try:
        result = scan_tradingview_symbols(
            [normalize_scan_symbol(symbol)],
            mcp_dir=Path(os.getenv("TRADINGVIEW_MCP_DIR", "/Users/kjun/code/tradingview-mcp")),
            bars=500,
            max_labels=250,
            timeframe="D",
            duplicate_window_bars=5,
            entry_policy="last",
            sleep_seconds=float(os.getenv("TRADINGVIEW_SINGLE_SCAN_SLEEP", "1.2")),
        )
    except Exception as exc:
        return "📡 Lazy Alpha 현재 상태\n판정: 확인 실패\n사유: " + str(exc)

    lines = ["📡 Lazy Alpha 현재 상태"]
    table = getattr(result, "table_snapshots", {}).get(normalize_scan_symbol(symbol))
    if result.outcomes:
        item = _latest_tradingview_outcome(result.outcomes)
        penalty = adjusted_priority_penalty(item)
        score = max(0, 100 - penalty)
        status = "매수 후보 유지" if penalty == 0 else f"주의 필요 · 감점 {penalty}"
        decision = evaluate_lazy_alpha_state(
            outcome_label=item.label,
            table_signal=table.signal if table else None,
            table_conviction=table.conviction if table else None,
            table_buy_eligibility=table.buy_eligibility if table else None,
            table_score=table.aux_score if table else None,
            penalty=penalty,
        )
        price_unit = "원" if item.market == "KR" else ""
        score_parts = [f"기술 {score}점"]
        if table and table.aux_score is not None:
            score_parts.append(f"Lazy {table.aux_score}점")
        if table and table.conviction:
            score_parts.append(f"확신 {table.conviction}")
        lines.extend(
            [
                "",
                "핵심 요약",
                f"최종판정: {decision.verdict} · {decision.reason}",
                f"다음 행동: {decision.action}",
                f"최근 신호: {item.signal_date} · {_compact_label(item.label)}",
                "점수: " + " · ".join(score_parts),
                "",
                "상세 근거",
                f"판정: {status}",
                f"기술점수: {score}점",
                f"시그널: {item.signal_date} · {_compact_label(item.label)}",
                f"신호 기준가: {_fmt_scan_price(item.entry_price)}{price_unit}",
                "확인: 이후 청산/SELL 라벨 없음",
            ]
        )
    elif result.exclusions:
        item = sorted(
            result.exclusions,
            key=lambda row: (row.exit_bar_index, row.entry_bar_index),
            reverse=True,
        )[0]
        exit_date = item.exit_date or "차트 우측 최신 라벨"
        decision = evaluate_lazy_alpha_state(
            exclusion_label=item.exit_label,
            table_signal=table.signal if table else None,
            table_conviction=table.conviction if table else None,
            table_buy_eligibility=table.buy_eligibility if table else None,
            table_score=table.aux_score if table else None,
            penalty=item.score_penalty_hint,
        )
        lines.extend(
            [
                "",
                "핵심 요약",
                f"최종판정: {decision.verdict} · {decision.reason}",
                f"다음 행동: {decision.action}",
                f"최근 신호: {exit_date} · {_compact_label(item.exit_label)}",
                f"직전 진입: {item.signal_date} · {_compact_label(item.label)}",
                "",
                "상세 근거",
                "판정: 매수 후보 아님",
                f"사유: {exit_date} · {_compact_label(item.exit_label)}",
                f"직전 진입: {item.signal_date} · {_compact_label(item.label)}",
            ]
        )
    else:
        decision = evaluate_lazy_alpha_state(
            table_signal=table.signal if table else None,
            table_conviction=table.conviction if table else None,
            table_buy_eligibility=table.buy_eligibility if table else None,
            table_score=table.aux_score if table else None,
        )
        lines.extend(
            [
                "",
                "핵심 요약",
                f"최종판정: {decision.verdict} · {decision.reason}",
                f"다음 행동: {decision.action}",
                "최근 신호: 없음",
                "",
                "상세 근거",
                "판정: 현재 매수 후보 아님",
                "사유: Lazy Alpha 진입 라벨 없음",
            ]
        )
    if result.errors:
        lines.append("오류: " + " · ".join(symbol for symbol, _error in result.errors[:3]))
    table_lines = _format_lazy_alpha_table(table)
    if table_lines:
        lines.extend(["", "Lazy 테이블", *table_lines])
    flow_lines = _format_label_flow(
        getattr(result, "label_flows", {}).get(normalize_scan_symbol(symbol), [])
    )
    if flow_lines:
        interpretation = interpret_lazy_alpha_flow(
            getattr(result, "label_flows", {}).get(normalize_scan_symbol(symbol), [])
        )
        lines.extend(["", "최근 1개월 라벨 흐름", *flow_lines])
        if interpretation:
            lines.extend(
                [
                    "",
                    "라벨 해석",
                    f"패턴: {interpretation.pattern} · {interpretation.confidence} · 점수영향 {interpretation.score_adjustment:+d}",
                    f"단계: {interpretation.stage}",
                    f"요약: {interpretation.summary}",
                    f"주의: {interpretation.risk}",
                    f"행동: {interpretation.action}",
                ]
            )
    return "\n".join(lines)


def _latest_tradingview_outcome(outcomes):
    return sorted(
        outcomes,
        key=lambda row: (row.last_signal_date, row.signal_date, row.symbol),
        reverse=True,
    )[0]


def _format_label_flow(flow_items) -> list[str]:
    if not flow_items:
        return []
    return [f"{item.date}  {_compact_label(item.label)}" for item in flow_items]


def _format_lazy_alpha_table(snapshot: TradingViewTableSnapshot | None) -> list[str]:
    if snapshot is None:
        return []
    lines: list[str] = []
    if snapshot.aux_score is not None or snapshot.conviction:
        score = f"{snapshot.aux_score}점" if snapshot.aux_score is not None else "-"
        conviction = snapshot.conviction or "-"
        lines.append(f"Lazy 점수: {score} · 확신 {conviction}")
    status_parts = [part for part in [snapshot.signal, snapshot.buy_eligibility] if part]
    if status_parts:
        lines.append("상태: " + " · ".join(status_parts))
    trend_parts = []
    if snapshot.ema_alignment:
        trend_parts.append(snapshot.ema_alignment)
    if snapshot.rs_score is not None:
        trend_parts.append(f"RS {snapshot.rs_score}점")
    if snapshot.volume_strength is not None:
        trend_parts.append(f"거래량 {snapshot.volume_strength:g}배")
    if snapshot.high_52w_pct is not None:
        trend_parts.append(f"52주고점 {snapshot.high_52w_pct:+g}%")
    if trend_parts:
        lines.append("추세: " + " · ".join(trend_parts))
    risk_parts = []
    if snapshot.stop_loss is not None:
        risk_parts.append(f"SL {_fmt_scan_price(snapshot.stop_loss)} ({_fmt_signed_pct(snapshot.stop_loss_pct)})")
    if snapshot.target_price is not None:
        risk_parts.append(f"TP1 {_fmt_scan_price(snapshot.target_price)} ({_fmt_signed_pct(snapshot.target_return_pct)})")
    if snapshot.risk_reward:
        risk_parts.append(f"R/R {snapshot.risk_reward}")
    if risk_parts:
        lines.append("리스크/보상: " + " · ".join(risk_parts))
    if snapshot.aux_signal:
        lines.append(f"보조 신호: {snapshot.aux_signal}")
    if snapshot.smart_eval:
        lines.append(f"평가: {snapshot.smart_eval}")
    if snapshot.fundamental:
        lines.append(f"펀더멘털: {snapshot.fundamental}")
    return lines


def _compact_label(text: str) -> str:
    return " / ".join(part.strip() for part in text.splitlines() if part.strip()) or "-"


def _fmt_scan_price(value: float) -> str:
    return f"{value:,.0f}" if value >= 100 else f"{value:.2f}"


def _fmt_signed_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:+g}%"


# ---------------------------------------------------------------------------
# 공통 조회 + 전송 헬퍼
# ---------------------------------------------------------------------------
async def _fetch_and_reply(
    update: Update,
    ticker: str,
    name: str,
    loading_message,
) -> None:
    """ticker로 fetch_all 실행 후 결과를 loading_message에 edit해 전송."""
    text = await asyncio.to_thread(render_stock_lookup_report, ticker, name)
    await loading_message.edit_text(text)


async def _lookup_and_reply(update: Update, query: str) -> None:
    """종목명 query를 검색하고, 후보 선택 또는 조회 결과를 응답한다."""
    query = query.strip()
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    logger.info("조회 트리거 수신: chat_id=%s query=%r", chat_id, query)
    if not query:
        await update.message.reply_text(
            "조회할 종목명을 같이 보내주세요.\n"
            "예) /s 삼성전자\n"
            "예) /s SK하이닉스"
        )
        return

    results = await asyncio.to_thread(search_ticker, query)

    if not results:
        await update.message.reply_text("종목을 찾을 수 없습니다.")
        return

    if len(results) == 1:
        item = results[0]
        loading_msg = await update.message.reply_text("🔍 조회 중...")
        await _fetch_and_reply(update, item["code"], item["name"], loading_msg)
        return

    buttons = [
        InlineKeyboardButton(
            f"{item['name']} ({item['market']})",
            callback_data=f"ticker:{item['code']}:{item['name']}",
        )
        for item in results[:5]
    ]
    keyboard = InlineKeyboardMarkup([[btn] for btn in buttons])
    await update.message.reply_text("종목을 선택해 주세요:", reply_markup=keyboard)


def _signal_store() -> SignalStore:
    return SignalStore(os.getenv("STATE_DB_PATH", "./state.db"))


def _transition_store() -> LazyAlphaTransitionStore:
    return LazyAlphaTransitionStore(os.getenv("STATE_DB_PATH", "./state.db"))


def _universe_snapshot_path() -> str:
    return os.getenv("UNIVERSE_SNAPSHOT_PATH", "./state/universe_snapshot.json")


def _load_universe_snapshot():
    return load_universe_snapshot(_universe_snapshot_path())


def _filter_rows_to_universe(rows):
    snapshot = _load_universe_snapshot()
    if snapshot is None:
        return rows
    return [row for row in rows if symbol_in_universe(row.ticker, snapshot)]


def render_universe_summary() -> str:
    return format_universe_summary(_load_universe_snapshot())


def render_sync_universe() -> str:
    snapshot = sync_universe_from_tradingview(
        mcp_dir=os.getenv("TRADINGVIEW_MCP_DIR", "/Users/kjun/code/tradingview-mcp"),
        output_path=_universe_snapshot_path(),
    )
    return "동기화 완료\n" + format_universe_summary(snapshot)


def assert_port_available(host: str, port: int) -> None:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        if sock.connect_ex((probe_host, port)) == 0:
            raise RuntimeError(f"port already in use: {host}:{port}")


def render_signal_console(args: list[str], *, now: int | None = None) -> tuple[str, InlineKeyboardMarkup]:
    current = int(now if now is not None else time.time())
    state = parse_console_args(args)
    store = _signal_store()
    rows = (
        store.active_signals(now=current)
        if state.view == "ACTIVE"
        else store.recent_since(current - state.hours * 3600)
    )
    rows = _filter_rows_to_universe(rows)
    return (
        format_console(rows=rows, state=state, now=current),
        build_console_keyboard(state),
    )


def render_signal_console_callback(data: str, *, now: int | None = None) -> tuple[str, InlineKeyboardMarkup]:
    current = int(now if now is not None else time.time())
    state = parse_console_callback(data)
    store = _signal_store()
    rows = (
        store.active_signals(now=current)
        if state.view == "ACTIVE"
        else store.recent_since(current - state.hours * 3600)
    )
    rows = _filter_rows_to_universe(rows)
    return (
        format_console(rows=rows, state=state, now=current),
        build_console_keyboard(state),
    )


def render_signal_detail(ticker: str, *, now: int | None = None) -> str:
    row = _signal_store().latest_for_ticker(ticker.strip())
    return format_signal_detail(row, now=now)


def render_tradingview_scan(args: list[str]) -> str:
    options = parse_tradingview_scan_args(args)
    result, batch_count = _scan_tradingview_symbols_batched(
        options["symbols"],
        batch_size=int(os.getenv("TRADINGVIEW_SCAN_BATCH_SIZE", "12")),
    )
    outcomes = result.outcomes
    if options["sort"] == "SCORE":
        outcomes = sorted(outcomes, key=priority_sort_key)
    enrichments = build_signal_enrichments(
        [*outcomes, *result.exclusions],
        supply_lookup=fetch_supply,
        fundamental_lookup=fetch_fundamental,
        audit_lookup=fetch_audit_firm,
    )
    return format_scan_report(
        outcomes=outcomes,
        exclusions=result.exclusions,
        errors=result.errors,
        scanned=result.scanned,
        enrichments=enrichments,
        table_snapshots=result.table_snapshots,
        label_flows=result.label_flows,
        title=options["title"],
        include_exclusions=options["include_exclusions"],
        requested_count=len(options["symbols"]),
        batch_count=batch_count,
    )


def render_lazy_alpha_transition_report(args: list[str]) -> str:
    options = parse_tradingview_scan_args(args)
    result, _batch_count = _scan_tradingview_symbols_batched(
        options["symbols"],
        batch_size=int(os.getenv("TRADINGVIEW_SCAN_BATCH_SIZE", "12")),
    )
    states = build_symbol_states_from_scan(result)
    transitions = _transition_store().record_states(states)
    return format_transition_report(
        transitions,
        scanned_count=len(result.scanned),
        errors=result.errors,
    )


def render_signal_recommendations(args: list[str]) -> str:
    scan_args = ["활성만", "점수", "50", *args]
    options = parse_tradingview_scan_args(scan_args)
    cooldown_skips = _recommendation_cooldown_skips(options)
    if not options.get("explicit_symbols"):
        options = {**options, "symbols": _recommendation_initial_symbols(options)}
    result, _batch_count = _scan_tradingview_symbols_batched(
        options["symbols"],
        batch_size=int(os.getenv("TRADINGVIEW_SCAN_BATCH_SIZE", "12")),
        use_cache=True,
        force_refresh=bool(options.get("sync")),
    )
    result = _supplement_recommendation_scan(options, result)
    _record_recommendation_errors(result.errors)
    enrichments = build_signal_enrichments(
        result.outcomes,
        supply_lookup=fetch_supply,
        fundamental_lookup=fetch_fundamental,
        audit_lookup=fetch_audit_firm,
    )
    candidates = recommend_signal_candidates(
        result.outcomes,
        enrichments=enrichments,
        label_flows=result.label_flows,
    )
    return format_recommendation_report(
        candidates,
        scanned=len(result.scanned),
        errors=result.errors,
        exclusions=result.exclusions,
        cooldown_skips=cooldown_skips,
        table_snapshots=result.table_snapshots,
    )


def render_recommendation_cooldown(args: list[str]) -> str:
    normalized_args = [arg.strip() for arg in args if arg.strip()]
    lowered_args = [arg.lower() for arg in normalized_args]
    if any(arg in {"해제", "삭제", "remove", "delete"} for arg in lowered_args) and len(normalized_args) >= 2:
        symbol = normalize_scan_symbol(normalized_args[-1])
        state = _read_recommendation_error_state()
        if symbol in state:
            del state[symbol]
            _write_recommendation_error_state(state)
            return f"🧊 추천 오류 심볼 쿨다운\n{symbol} 해제 완료"
        return f"🧊 추천 오류 심볼 쿨다운\n{symbol}은 현재 쿨다운 상태가 아닙니다."

    if any(arg in {"초기화", "clear", "reset"} for arg in lowered_args):
        _write_recommendation_error_state({})
        return "🧊 추천 오류 심볼 쿨다운\n초기화 완료"

    ttl = int(os.getenv("RECOMMENDATION_ERROR_COOLDOWN_SECONDS", str(6 * 3600)))
    now = int(time.time())
    rows = []
    active_state = {}
    state = _read_recommendation_error_state()
    for symbol, payload in state.items():
        failed_at = int(payload.get("last_failed_at", 0))
        remaining = ttl - (now - failed_at)
        if remaining <= 0:
            continue
        active_state[symbol] = payload
        rows.append((symbol, remaining, str(payload.get("error") or "-")))
    if len(active_state) != len(state):
        _write_recommendation_error_state(active_state)
    rows.sort(key=lambda item: (item[1], item[0]))

    lines = [
        "🧊 추천 오류 심볼 쿨다운",
        f"활성: {len(rows)}건 · TTL {ttl // 3600 if ttl >= 3600 else ttl // 60}{'시간' if ttl >= 3600 else '분'}",
    ]
    if not rows:
        lines.extend(["", "현재 쿨다운 중인 오류 심볼이 없습니다."])
        return "\n".join(lines)
    lines.append("")
    for index, (symbol, remaining, error) in enumerate(rows[:20], start=1):
        lines.append(f"{index}. {symbol} · 남은 {_fmt_duration_ko(remaining)} · {error}")
    lines.extend(["", "초기화: /추천쿨다운 초기화"])
    return "\n".join(lines)


def _supplement_recommendation_scan(options: dict, result: TradingViewScanResult) -> TradingViewScanResult:
    market = options.get("market")
    requested = list(options.get("symbols") or [])
    target = int(options.get("limit") or len(requested) or 1)
    if not market or len(result.outcomes) >= target or options.get("explicit_symbols"):
        return result
    max_attempts = _recommendation_max_attempts(target)
    universe_symbols = _recommendation_symbol_pool(
        market=market,
        limit=max_attempts,
        ignore_error_cooldown=bool(options.get("sync")),
    )
    seen = {symbol for symbol in requested}
    seen.update(symbol for symbol, _error in result.errors)
    seen.update(result.scanned)
    supplements = [symbol for symbol in universe_symbols if symbol not in seen]
    if not supplements:
        return result
    remaining_attempts = max(0, max_attempts - len(seen))
    batch_size = max(1, int(os.getenv("TRADINGVIEW_SCAN_BATCH_SIZE", "12")))
    merged = result
    for index in range(0, min(len(supplements), remaining_attempts), batch_size):
        if len(merged.outcomes) >= target:
            break
        chunk = supplements[index : index + batch_size]
        if not chunk:
            break
        supplement_result, _batch_count = _scan_tradingview_symbols_batched(
            chunk,
            batch_size=batch_size,
            use_cache=True,
            force_refresh=bool(options.get("sync")),
        )
        merged = _merge_scan_results([merged, supplement_result])
    return merged


def _recommendation_initial_symbols(options: dict) -> list[str]:
    symbols = list(options.get("symbols") or [])
    market = options.get("market")
    if not market:
        if options.get("sync"):
            return symbols
        return _filter_recommendation_error_cooldown(symbols) or symbols
    target = int(options.get("limit") or len(symbols) or 1)
    pool = _recommendation_symbol_pool(
        market=market,
        limit=_recommendation_max_attempts(target),
        ignore_error_cooldown=bool(options.get("sync")),
    )
    return pool[:target] if pool else symbols


def _recommendation_symbol_pool(*, market: str, limit: int, ignore_error_cooldown: bool) -> list[str]:
    symbols = symbols_from_universe(Path(_universe_snapshot_path()), limit=limit, market=market)
    if ignore_error_cooldown:
        return symbols
    return _filter_recommendation_error_cooldown(symbols)


def _recommendation_cooldown_skips(options: dict) -> list[str]:
    if options.get("sync") or options.get("explicit_symbols"):
        return []
    active = _active_recommendation_error_symbols()
    if not active:
        return []
    market = options.get("market")
    if market:
        target = int(options.get("limit") or len(options.get("symbols") or []) or 1)
        symbols = symbols_from_universe(
            Path(_universe_snapshot_path()),
            limit=_recommendation_max_attempts(target),
            market=market,
        )
    else:
        symbols = list(options.get("symbols") or [])
    return [symbol for symbol in symbols if symbol in active]


def _recommendation_max_attempts(target: int) -> int:
    multiplier = int(os.getenv("RECOMMENDATION_SCAN_FALLBACK_MULTIPLIER", "3"))
    max_attempts = max(target + 2, target * multiplier)
    configured_max_attempts = os.getenv("RECOMMENDATION_SCAN_MAX_ATTEMPTS")
    if configured_max_attempts:
        max_attempts = max(target, int(configured_max_attempts))
    return max_attempts


def _filter_recommendation_error_cooldown(symbols: list[str]) -> list[str]:
    active = _active_recommendation_error_symbols()
    if not active:
        return symbols
    return [symbol for symbol in symbols if symbol not in active]


def _active_recommendation_error_symbols() -> set[str]:
    ttl = int(os.getenv("RECOMMENDATION_ERROR_COOLDOWN_SECONDS", str(6 * 3600)))
    now = int(time.time())
    return {
        symbol
        for symbol, payload in _read_recommendation_error_state().items()
        if now - int(payload.get("last_failed_at", 0)) <= ttl
    }


def _record_recommendation_errors(errors: list[tuple[str, str]]) -> None:
    if not errors:
        return
    state = _read_recommendation_error_state()
    now = int(time.time())
    for symbol, error in errors:
        state[symbol] = {"last_failed_at": now, "error": str(error)}
    _write_recommendation_error_state(state)


def _read_recommendation_error_state() -> dict[str, dict]:
    path = Path(os.getenv("RECOMMENDATION_ERROR_COOLDOWN_PATH", "./state/recommendation_symbol_errors.json"))
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(symbol): dict(value) for symbol, value in payload.items() if isinstance(value, dict)}


def _write_recommendation_error_state(state: dict[str, dict]) -> None:
    path = Path(os.getenv("RECOMMENDATION_ERROR_COOLDOWN_PATH", "./state/recommendation_symbol_errors.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _fmt_duration_ko(seconds: int) -> str:
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f"{minutes}분"
    hours, rest_minutes = divmod(minutes, 60)
    if rest_minutes == 0:
        return f"{hours}시간"
    return f"{hours}시간 {rest_minutes}분"


def _scan_tradingview_symbols_batched(
    symbols: list[str],
    *,
    batch_size: int,
    use_cache: bool = False,
    force_refresh: bool = False,
) -> tuple[TradingViewScanResult, int]:
    safe_batch_size = max(1, batch_size)
    chunks = [symbols[index : index + safe_batch_size] for index in range(0, len(symbols), safe_batch_size)] or [[]]
    results = [
        _scan_tradingview_chunk(
            chunk,
            use_cache=use_cache,
            force_refresh=force_refresh,
        )
        for chunk in chunks
        if chunk
    ]
    if not results:
        return TradingViewScanResult(outcomes=[], exclusions=[], errors=[], scanned=[], label_flows={}, table_snapshots={}), 0
    return (
        _merge_scan_results(results),
        len(results),
    )


def _scan_tradingview_chunk(
    symbols: list[str],
    *,
    use_cache: bool,
    force_refresh: bool,
) -> TradingViewScanResult:
    context = {
        "bars": 500,
        "max_labels": 250,
        "timeframe": "D",
        "entry_policy": "last",
    }
    cache = _tradingview_scan_cache() if use_cache else None
    if cache is not None and not force_refresh:
        cached = cache.get(symbols=symbols, context=context)
        if cached is not None:
            return cached
    result = scan_tradingview_symbols(
        symbols,
        mcp_dir=Path(os.getenv("TRADINGVIEW_MCP_DIR", "/Users/kjun/code/tradingview-mcp")),
        sleep_seconds=float(os.getenv("TRADINGVIEW_SCAN_SLEEP", "2.0")),
        **context,
    )
    if cache is not None:
        cache.set(symbols=symbols, context=context, result=result)
    return result


def _tradingview_scan_cache() -> TradingViewScanCache:
    return TradingViewScanCache(
        os.getenv("TRADINGVIEW_SCAN_CACHE_PATH", "./state/tradingview_scan_cache.sqlite3"),
        ttl_seconds=int(os.getenv("TRADINGVIEW_SCAN_CACHE_TTL_SECONDS", "600")),
    )


def _merge_scan_results(results: list[TradingViewScanResult]) -> TradingViewScanResult:
    return TradingViewScanResult(
        outcomes=[item for result in results for item in result.outcomes],
        exclusions=[item for result in results for item in result.exclusions],
        errors=[item for result in results for item in result.errors],
        scanned=[item for result in results for item in result.scanned],
        label_flows={key: value for result in results for key, value in result.label_flows.items()},
        table_snapshots={key: value for result in results for key, value in result.table_snapshots.items()},
    )


def render_leading_discovery(args: list[str]) -> str:
    options = parse_leading_discovery_args(args)
    candidates: list[LeadingCandidate] = []
    errors: list[tuple[str, str]] = []
    symbols = _leading_kr_symbol_pool(options["limit"], use_universe=options["use_universe"])
    name_map = _ticker_name_map()
    for symbol in symbols:
        ticker = symbol.removeprefix("KRX:")
        name = name_map.get(ticker, ticker)
        try:
            supply = fetch_supply(ticker)
            technical = fetch_technical(ticker)
            fundamental = fetch_fundamental(ticker)
            audit = fetch_audit_firm(ticker)
            candidates.append(
                score_leading_candidate(
                    symbol=symbol,
                    name=name,
                    supply=supply,
                    technical=technical,
                    fundamental=fundamental,
                    auditor=_leading_auditor_summary(audit),
                )
            )
        except Exception as exc:
            errors.append((symbol, str(exc)))
    return format_leading_report(
        candidates,
        scanned=len(symbols),
        errors=errors,
        limit=options["output_limit"],
    )


def render_backtest_report(
    args: list[str],
    *,
    price_provider: PriceHistoryProvider | None = None,
) -> str:
    options = parse_backtest_args(args)
    rows = [
        row
        for row in _signal_store().events_for_audit(limit=options["limit"], action="BUY")
        if row.market == options["market"]
    ]
    outcomes = audit_signal_outcomes(
        rows,
        price_provider=price_provider or _price_history_provider(),
    )
    return format_calibration_report(outcomes)


def _price_history_provider() -> PriceHistoryProvider:
    base = MarketPriceHistoryProvider(
        tradingview_provider=TradingViewPriceHistoryProvider(
            mcp_dir=Path(os.getenv("TRADINGVIEW_MCP_DIR", "/Users/kjun/code/tradingview-mcp")),
            bars=int(os.getenv("PRICE_HISTORY_TRADINGVIEW_BARS", "900")),
            sleep_seconds=float(os.getenv("PRICE_HISTORY_TRADINGVIEW_SLEEP", "1.0")),
        )
    )
    return CachedPriceHistoryProvider(
        base,
        db_path=os.getenv("PRICE_HISTORY_CACHE_DB", os.getenv("STATE_DB_PATH", "./state.db")),
        ttl_seconds=int(os.getenv("PRICE_HISTORY_CACHE_TTL_SECONDS", str(6 * 3600))),
    )


def parse_backtest_args(args: list[str]) -> dict:
    market = "KR"
    limit = 50
    for arg in args:
        lowered = arg.strip().lower()
        if not lowered:
            continue
        if lowered in {"kr", "국장", "korea"}:
            market = "KR"
            continue
        if lowered in {"us", "미장", "usa"}:
            market = "US"
            continue
        if lowered in {"jp", "일본", "japan"}:
            market = "JP"
            continue
        if lowered.isdigit():
            limit = max(1, min(int(lowered), 300))
    return {"market": market, "limit": limit}


def parse_leading_discovery_args(args: list[str]) -> dict:
    limit = 25
    output_limit = 12
    use_universe = False
    for arg in args:
        lowered = arg.strip().lower()
        if lowered in {"", "kr", "국장", "korea"}:
            continue
        if lowered in {"관심", "universe", "watchlist", "watchlists"}:
            use_universe = True
            continue
        if lowered.isdigit():
            limit = max(1, min(int(lowered), 80))
            output_limit = max(1, min(int(lowered), 20))
    return {"market": "KR", "limit": limit, "output_limit": output_limit, "use_universe": use_universe}


def _leading_kr_symbol_pool(limit: int, *, use_universe: bool) -> list[str]:
    symbols: list[str] = []
    if use_universe:
        snapshot = _load_universe_snapshot()
        if snapshot is not None:
            symbols.extend(
                symbol
                for symbol, meta in snapshot.symbols.items()
                if symbol.startswith("KRX:") and meta.asset_type == "EQUITY"
            )
    symbols.extend(seed.symbol for seed in KR_CANDIDATE_SEEDS)
    deduped = list(dict.fromkeys(symbols))
    return deduped[:limit]


def _ticker_name_map() -> dict[str, str]:
    try:
        return {str(item["code"]): str(item["name"]) for item in load_ticker_cache()}
    except Exception:
        return {seed.symbol.removeprefix("KRX:"): seed.name for seed in KR_CANDIDATE_SEEDS}


def _leading_auditor_summary(audit: dict) -> str:
    labels = {
        "BLOCKED_CONFIRMED": "독립성 차단",
        "BLOCKED_POSSIBLE": "독립성 차단 가능",
        "CLEAR_CONFIRMED": "차단 없음",
        "ROLLOVER_INFERRED": "감사인 추정 확인 필요",
        "MANUAL_VERIFY_CURRENT_YEAR": "현재연도 감사인 확인 필요",
        "DATA_MISSING": "감사인 데이터 없음",
    }
    decision = decide_independence(Market("KR", "한국"), audit)
    return f"{labels.get(decision.status, decision.status)} · {decision.auditor or '-'}"


def parse_tradingview_scan_args(args: list[str]) -> dict:
    market: str | None = None
    limit = 5
    sort = "TIME"
    sync = False
    full_universe = False
    include_exclusions = True
    title = "📡 TradingView 직접 스캔"
    symbols: list[str] = []
    for arg in args:
        value = arg.strip()
        lowered = value.lower()
        if not value or lowered in {"관심", "universe", "watchlist", "watchlists"}:
            continue
        if lowered in {"전체", "모두", "all", "full"}:
            full_universe = True
            limit = int(os.getenv("TRADINGVIEW_SCAN_FULL_LIMIT", "120"))
            title = "📡 TradingView 전체 Watchlist 스캔"
            continue
        if lowered in {"sync", "동기화", "현재"}:
            sync = True
            continue
        if lowered in {"kr", "국장", "korea"}:
            market = "KR"
            continue
        if lowered in {"us", "미장", "usa"}:
            market = "US"
            continue
        if lowered in {"jp", "일본", "japan"}:
            market = "JP"
            continue
        if lowered in {"점수", "점수순", "score", "scores", "rank"}:
            sort = "SCORE"
            continue
        if lowered in {"활성", "활성만", "진입", "매수", "entry", "entries", "active", "buyonly"}:
            include_exclusions = False
            title = "📡 현재 진입/매수 후보"
            continue
        if lowered.isdigit() and len(lowered) != 6:
            limit = max(1, min(int(lowered), 50))
            continue
        symbols.append(normalize_scan_symbol(value))

    explicit_symbols = bool(symbols)
    if not symbols:
        if sync:
            sync_universe_from_tradingview(
                mcp_dir=os.getenv("TRADINGVIEW_MCP_DIR", "/Users/kjun/code/tradingview-mcp"),
                output_path=_universe_snapshot_path(),
            )
        symbols = symbols_from_universe(Path(_universe_snapshot_path()), limit=limit, market=market)
    else:
        symbols = symbols[:limit]
    return {
        "symbols": symbols,
        "market": market,
        "limit": limit,
        "sort": sort,
        "sync": sync,
        "full_universe": full_universe,
        "include_exclusions": include_exclusions,
        "title": title,
        "explicit_symbols": explicit_symbols,
    }


def is_help_text(text: str) -> bool:
    return text.strip().lower() in _HELP_TEXT_SHORTCUTS


def is_signal_console_text(text: str) -> bool:
    return text.strip().lower() in _SIGNAL_CONSOLE_TEXT_SHORTCUTS


def parse_signal_console_text(text: str) -> list[str] | None:
    command, args = _strip_korean_slash_command(text)
    normalized = command.strip().lower()
    if normalized in {"신호", "시그널", "signals", "signal"}:
        return args
    return None


def parse_tradingview_scan_text(text: str) -> list[str] | None:
    command, args = _strip_korean_slash_command(text)
    normalized = command.strip().lower()
    if normalized in {"국장스캔", "krscan"}:
        return ["국장", "점수", "50", "동기화", *args]
    if normalized in {"진입", "매수", "entry", "entries"}:
        return ["활성만", "점수", "50", "동기화", *args]
    if normalized in _TRADINGVIEW_SCAN_TEXT_SHORTCUTS:
        return args
    return None


def parse_lazy_alpha_transition_text(text: str) -> list[str] | None:
    command, args = _strip_korean_slash_command(text)
    normalized = command.strip().lower()
    if normalized in _LAZY_ALPHA_TRANSITION_TEXT_SHORTCUTS:
        return args
    return None


def parse_leading_discovery_text(text: str) -> list[str] | None:
    command, args = _strip_korean_slash_command(text)
    normalized = command.strip().lower()
    if normalized in _LEADING_DISCOVERY_TEXT_SHORTCUTS:
        return args
    return None


def parse_backtest_text(text: str) -> list[str] | None:
    command, args = _strip_korean_slash_command(text)
    normalized = command.strip().lower()
    if normalized in _BACKTEST_TEXT_SHORTCUTS:
        return args
    return None


def parse_recommendation_text(text: str) -> list[str] | None:
    command, args = _strip_korean_slash_command(text)
    normalized = command.strip().lower()
    if normalized in _RECOMMENDATION_TEXT_SHORTCUTS:
        return args
    return None


def parse_recommendation_cooldown_text(text: str) -> list[str] | None:
    command, args = _strip_korean_slash_command(text)
    normalized = command.strip().lower()
    if normalized in _RECOMMENDATION_COOLDOWN_TEXT_SHORTCUTS:
        return args
    return None


# ---------------------------------------------------------------------------
# 핸들러
# ---------------------------------------------------------------------------
def _fmt_feed(signals: list[dict]) -> str:
    if not signals:
        return "📋 최근 BUY 시그널 없음"
    lines = [f"📋 최근 BUY 시그널 ({len(signals)}건)\n"]
    for sig in signals:
        payload = sig.get("payload") or {}
        name = payload.get("name", sig["ticker"])
        ticker = payload.get("ticker", sig["ticker"])
        tf = sig.get("timeframe", "?")
        type_ = sig.get("type", "?")
        score = payload.get("score", "-")
        conviction = payload.get("conviction", "-")
        price = payload.get("price")
        price_str = f"{price:,.0f}원" if price else "-"

        # received_at: ISO → KST readable
        received_raw = sig.get("received_at", "")
        try:
            dt = datetime.fromisoformat(received_raw).astimezone(_KST)
            received = dt.strftime("%m/%d %H:%M")
        except Exception:
            received = received_raw[:16] if received_raw else "-"

        lines.append(
            f"• {name} ({ticker})  {tf}분봉\n"
            f"  {type_}  |  Score {score}  |  {conviction}등급  |  {price_str}\n"
            f"  {received} KST"
        )
    return "\n\n".join(lines)


async def handle_feed(update: Update, context) -> None:
    """/feed — 최근 BUY 시그널 목록 (02 audit-safe-signals 연동)."""
    if not await check_allowed(update):
        return

    if not _SIGNALS_URL:
        await update.message.reply_text("ASS_SIGNALS_URL 환경변수가 설정되지 않았습니다.")
        return

    limit = 20
    if context.args:
        try:
            limit = max(1, min(int(context.args[0]), 50))
        except ValueError:
            pass

    loading = await update.message.reply_text("📡 시그널 조회 중...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                _SIGNALS_URL,
                params={"secret": _SIGNALS_SECRET, "limit": limit},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.exception("feed fetch failed")
        await loading.edit_text(f"⚠️ 조회 실패: {exc!s}")
        return

    text = _fmt_feed(data.get("signals", []))
    await loading.edit_text(text)


async def handle_signal_console(update: Update, context) -> None:
    """/signals — Lazy Alpha 시그널 버튼 콘솔."""
    if not await check_allowed(update):
        return

    text, keyboard = await asyncio.to_thread(render_signal_console, list(context.args))
    await update.message.reply_text(text, reply_markup=keyboard)


async def handle_buy_console(update: Update, context) -> None:
    """/buy — 최근 매수 후보."""
    if not await check_allowed(update):
        return

    text, keyboard = await asyncio.to_thread(
        render_signal_console,
        ["buy", *list(context.args)],
    )
    await update.message.reply_text(text, reply_markup=keyboard)


async def handle_sell_console(update: Update, context) -> None:
    """/sell — 최근 매도 후보."""
    if not await check_allowed(update):
        return

    text, keyboard = await asyncio.to_thread(
        render_signal_console,
        ["sell", *list(context.args)],
    )
    await update.message.reply_text(text, reply_markup=keyboard)


async def handle_signal_detail(update: Update, context) -> None:
    """/signal <ticker> — 특정 종목 최신 Lazy Alpha 판단."""
    if not await check_allowed(update):
        return

    ticker = " ".join(context.args).strip()
    if not ticker:
        await update.message.reply_text("조회할 종목코드를 같이 보내주세요.\n예) /signal 005930")
        return
    text = await asyncio.to_thread(render_signal_detail, ticker)
    await update.message.reply_text(text)


def _strip_korean_slash_command(text: str) -> tuple[str, list[str]]:
    parts = text.strip().split()
    command = parts[0].split("@", 1)[0].lstrip("/") if parts else ""
    return command, parts[1:]


async def handle_korean_signal_command(update: Update, context) -> None:
    """/신호 텍스트 트리거. Telegram command menu 제약과 무관하게 직접 입력을 지원한다."""
    if not await check_allowed(update):
        return

    _command, args = _strip_korean_slash_command(update.message.text)
    text, keyboard = await asyncio.to_thread(render_signal_console, args or ["buy"])
    await update.message.reply_text(text, reply_markup=keyboard)


async def handle_tradingview_scan_command(update: Update, context) -> None:
    """/스캔 텍스트 트리거. TradingView 차트에서 Lazy Alpha 라벨을 직접 읽는다."""
    if not await check_allowed(update):
        return

    command, args = _strip_korean_slash_command(update.message.text)
    if command.lower() in {"진입", "매수", "entry", "entries"}:
        args = ["활성만", "점수", "50", "동기화", *args]
    loading = await update.message.reply_text("📡 TradingView 직접 스캔 중... 차트를 순차 확인합니다.")
    try:
        text = await asyncio.to_thread(render_tradingview_scan, args)
    except Exception as exc:
        logger.exception("tradingview direct scan failed")
        await loading.edit_text(f"⚠️ TradingView 직접 스캔 실패: {exc!s}")
        return
    await loading.edit_text(_truncate_telegram_text(text))


async def handle_lazy_alpha_transition_command(update: Update, context) -> None:
    """/변화 텍스트 트리거. 이전 스캔 대비 Lazy Alpha 상태 전환만 보여준다."""
    if not await check_allowed(update):
        return

    _command, args = _strip_korean_slash_command(update.message.text)
    loading = await update.message.reply_text("🔔 Lazy Alpha 상태 변화 확인 중... 이전 관측과 비교합니다.")
    try:
        text = await asyncio.to_thread(render_lazy_alpha_transition_report, args or ["kr"])
    except Exception as exc:
        logger.exception("lazy alpha transition scan failed")
        await loading.edit_text(f"⚠️ 상태 변화 확인 실패: {exc!s}")
        return
    await loading.edit_text(_truncate_telegram_text(text))


async def handle_recommendation_command(update: Update, context) -> None:
    """/추천 텍스트 트리거. 활성 Lazy Alpha 매수 라벨 중 시세반영 전 후보를 압축한다."""
    if not await check_allowed(update):
        return

    _command, args = _strip_korean_slash_command(update.message.text)
    loading = await update.message.reply_text("🎯 추천 후보 스캔 중... 활성 라벨과 시세반영 정도를 함께 봅니다.")
    try:
        text = await asyncio.to_thread(render_signal_recommendations, args or ["kr"])
    except Exception as exc:
        logger.exception("signal recommendation scan failed")
        await loading.edit_text(f"⚠️ 추천 후보 스캔 실패: {exc!s}")
        return
    await loading.edit_text(_truncate_telegram_text(text))


async def handle_recommendation_cooldown_command(update: Update, context) -> None:
    """/추천쿨다운 텍스트 트리거. 추천 스캔 오류 심볼 쿨다운을 조회/초기화한다."""
    if not await check_allowed(update):
        return

    _command, args = _strip_korean_slash_command(update.message.text)
    text = await asyncio.to_thread(render_recommendation_cooldown, args)
    await update.message.reply_text(_truncate_telegram_text(text))


async def handle_leading_discovery_command(update: Update, context) -> None:
    """/선행 텍스트 트리거. 수급+기술 전조로 국장 선행 후보를 압축한다."""
    if not await check_allowed(update):
        return

    _command, args = _strip_korean_slash_command(update.message.text)
    loading = await update.message.reply_text("🔎 국장 선행 후보 스캔 중... 수급과 차트 전조를 확인합니다.")
    try:
        text = await asyncio.to_thread(render_leading_discovery, args or ["kr"])
    except Exception as exc:
        logger.exception("leading discovery failed")
        await loading.edit_text(f"⚠️ 선행 후보 스캔 실패: {exc!s}")
        return
    await loading.edit_text(_truncate_telegram_text(text))


async def handle_backtest_command(update: Update, context) -> None:
    """/검증 텍스트 트리거. 저장된 BUY 웹훅 시그널의 이후 가격 흐름을 점수대별로 요약한다."""
    if not await check_allowed(update):
        return

    _command, args = _strip_korean_slash_command(update.message.text)
    loading = await update.message.reply_text("🧪 저장된 BUY 시그널 사후검증 중...")
    try:
        text = await asyncio.to_thread(render_backtest_report, args or ["kr"])
    except Exception as exc:
        logger.exception("signal backtest failed")
        await loading.edit_text(f"⚠️ 사후검증 실패: {exc!s}")
        return
    await loading.edit_text(_truncate_telegram_text(text))


async def handle_korean_stock_command(update: Update, context) -> None:
    """/종목 텍스트 트리거. 종목 리서치와 현재 TradingView Lazy Alpha 판단을 함께 보여준다."""
    if not await check_allowed(update):
        return

    _command, args = _strip_korean_slash_command(update.message.text)
    query = " ".join(args).strip()
    if not query:
        await update.message.reply_text("조회할 종목명이나 종목코드를 같이 보내주세요.\n예) /종목 005930")
        return

    await _lookup_and_reply(update, query)


async def handle_signal_console_callback(update: Update, context) -> None:
    """Lazy Alpha console inline keyboard callback."""
    query = update.callback_query
    await query.answer()

    if not await check_allowed(update):
        return

    text, keyboard = await asyncio.to_thread(render_signal_console_callback, query.data)
    await query.edit_message_text(text, reply_markup=keyboard)


async def handle_universe(update: Update, context) -> None:
    """/universe — TradingView watchlist universe summary."""
    if not await check_allowed(update):
        return

    text = await asyncio.to_thread(render_universe_summary)
    await update.message.reply_text(text)


async def handle_sync_universe(update: Update, context) -> None:
    """/sync_universe — sync TradingView watchlists into local universe."""
    if not await check_allowed(update):
        return

    loading = await update.message.reply_text("🌐 TradingView watchlist universe 동기화 중...")
    try:
        text = await asyncio.to_thread(render_sync_universe)
    except Exception as exc:
        logger.exception("universe sync failed")
        await loading.edit_text(f"⚠️ universe 동기화 실패: {exc!s}")
        return
    await loading.edit_text(text)


async def handle_start(update: Update, context) -> None:
    """/start 커맨드 핸들러."""
    if not await check_allowed(update):
        return

    await update.message.reply_text(HELP_TEXT)


async def handle_ping(update: Update, context) -> None:
    """/ping 헬스체크 핸들러."""
    if not await check_allowed(update):
        return

    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    logger.info("ping 수신: chat_id=%s", chat_id)
    await update.message.reply_text("pong")


async def handle_lookup_command(update: Update, context) -> None:
    """/stock, /s, /check 커맨드 핸들러."""
    if not await check_allowed(update):
        return

    query = " ".join(context.args).strip()
    await _lookup_and_reply(update, query)


async def handle_korean_lookup_text(update: Update, context) -> None:
    """/조회 텍스트 트리거 핸들러. DM에서 편의용으로 지원한다."""
    if not await check_allowed(update):
        return

    text = update.message.text.strip()
    query = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""
    await _lookup_and_reply(update, query)


async def handle_text(update: Update, context) -> None:
    """텍스트 메시지 핸들러: 종목명 입력 → 검색 → 결과 분기."""
    if not await check_allowed(update):
        return

    query = update.message.text.strip()
    if is_help_text(query):
        await update.message.reply_text(HELP_TEXT)
        return
    signal_args = parse_signal_console_text(query)
    if signal_args is not None:
        text, keyboard = await asyncio.to_thread(render_signal_console, signal_args or [])
        await update.message.reply_text(text, reply_markup=keyboard)
        return
    scan_args = parse_tradingview_scan_text(query)
    if scan_args is not None:
        loading = await update.message.reply_text("📡 TradingView 직접 스캔 중... 차트를 순차 확인합니다.")
        try:
            text = await asyncio.to_thread(render_tradingview_scan, scan_args)
        except Exception as exc:
            logger.exception("tradingview direct scan failed")
            await loading.edit_text(f"⚠️ TradingView 직접 스캔 실패: {exc!s}")
            return
        await loading.edit_text(_truncate_telegram_text(text))
        return
    transition_args = parse_lazy_alpha_transition_text(query)
    if transition_args is not None:
        loading = await update.message.reply_text("🔔 Lazy Alpha 상태 변화 확인 중... 이전 관측과 비교합니다.")
        try:
            text = await asyncio.to_thread(render_lazy_alpha_transition_report, transition_args or ["kr"])
        except Exception as exc:
            logger.exception("lazy alpha transition scan failed")
            await loading.edit_text(f"⚠️ 상태 변화 확인 실패: {exc!s}")
            return
        await loading.edit_text(_truncate_telegram_text(text))
        return
    recommendation_args = parse_recommendation_text(query)
    if recommendation_args is not None:
        loading = await update.message.reply_text("🎯 추천 후보 스캔 중... 활성 라벨과 시세반영 정도를 함께 봅니다.")
        try:
            text = await asyncio.to_thread(render_signal_recommendations, recommendation_args or ["kr"])
        except Exception as exc:
            logger.exception("signal recommendation scan failed")
            await loading.edit_text(f"⚠️ 추천 후보 스캔 실패: {exc!s}")
            return
        await loading.edit_text(_truncate_telegram_text(text))
        return
    cooldown_args = parse_recommendation_cooldown_text(query)
    if cooldown_args is not None:
        text = await asyncio.to_thread(render_recommendation_cooldown, cooldown_args)
        await update.message.reply_text(_truncate_telegram_text(text))
        return
    leading_args = parse_leading_discovery_text(query)
    if leading_args is not None:
        loading = await update.message.reply_text("🔎 국장 선행 후보 스캔 중... 수급과 차트 전조를 확인합니다.")
        try:
            text = await asyncio.to_thread(render_leading_discovery, leading_args or ["kr"])
        except Exception as exc:
            logger.exception("leading discovery failed")
            await loading.edit_text(f"⚠️ 선행 후보 스캔 실패: {exc!s}")
            return
        await loading.edit_text(_truncate_telegram_text(text))
        return
    backtest_args = parse_backtest_text(query)
    if backtest_args is not None:
        loading = await update.message.reply_text("🧪 저장된 BUY 시그널 사후검증 중...")
        try:
            text = await asyncio.to_thread(render_backtest_report, backtest_args or ["kr"])
        except Exception as exc:
            logger.exception("signal backtest failed")
            await loading.edit_text(f"⚠️ 사후검증 실패: {exc!s}")
            return
        await loading.edit_text(_truncate_telegram_text(text))
        return
    await _lookup_and_reply(update, query)


def _truncate_telegram_text(text: str, *, limit: int = 3900) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 40].rstrip() + "\n\n... 일부 결과 생략"


async def handle_callback(update: Update, context) -> None:
    """InlineKeyboard 버튼 클릭 핸들러."""
    query = update.callback_query
    await query.answer()

    if not await check_allowed(update):
        return

    # callback_data: "ticker:{code}:{name}"
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await query.edit_message_text("잘못된 요청입니다.")
        return

    _, ticker, name = parts

    await query.edit_message_text("🔍 조회 중...")
    text = await asyncio.to_thread(render_stock_lookup_report, ticker, name)
    await query.edit_message_text(text)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
async def post_init(application: Application) -> None:
    if os.getenv("LAZY_ALPHA_TRANSITION_ALERT_ENABLED", "0") in {"1", "true", "True", "yes"}:
        scheduler.add_job(
            _scheduled_lazy_alpha_transition_alert,
            CronTrigger(
                hour=int(os.getenv("LAZY_ALPHA_TRANSITION_ALERT_HOUR", "16")),
                minute=int(os.getenv("LAZY_ALPHA_TRANSITION_ALERT_MINUTE", "10")),
                timezone=_KST,
            ),
            id="lazy_alpha_transition_alert",
            replace_existing=True,
        )
    scheduler.start()
    logger.info("봇 시작. 종목 캐시 갱신 스케줄: 매일 07:00 KST")


async def _run() -> None:
    """Telegram polling + FastAPI alert server 동시 실행."""
    import uvicorn

    from alert_server import app as alert_app

    tg_app = Application.builder().token(TOKEN).post_init(post_init).build()
    tg_app.add_handler(CommandHandler("start", handle_start))
    tg_app.add_handler(CommandHandler("ping", handle_ping))
    tg_app.add_handler(CommandHandler("feed", handle_feed))
    tg_app.add_handler(CommandHandler("signals", handle_signal_console))
    tg_app.add_handler(CommandHandler("universe", handle_universe))
    tg_app.add_handler(CommandHandler(["sync_universe", "syncuniverse"], handle_sync_universe))
    tg_app.add_handler(CommandHandler("buy", handle_buy_console))
    tg_app.add_handler(CommandHandler("sell", handle_sell_console))
    tg_app.add_handler(CommandHandler("signal", handle_signal_detail))
    tg_app.add_handler(CommandHandler(["leading", "discover"], handle_leading_discovery_command))
    tg_app.add_handler(CommandHandler(["entry", "entries"], handle_tradingview_scan_command))
    tg_app.add_handler(CommandHandler(["recommend", "recommendations", "pick", "picks"], handle_recommendation_command))
    tg_app.add_handler(CommandHandler(["recommend_cooldown", "cooldown"], handle_recommendation_cooldown_command))
    tg_app.add_handler(CommandHandler(["tvscan", "scan"], handle_tradingview_scan_command))
    tg_app.add_handler(CommandHandler(["changes", "transition", "transitions"], handle_lazy_alpha_transition_command))
    tg_app.add_handler(CommandHandler(["backtest", "audit"], handle_backtest_command))
    tg_app.add_handler(CommandHandler(["stock", "s", "check"], handle_lookup_command))
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/조회(?:@\S+)?(?:\s+.*)?$"),
            handle_korean_lookup_text,
        )
    )
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/신호(?:@\S+)?(?:\s+.*)?$"),
            handle_korean_signal_command,
        )
    )
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/(?:스캔|현재신호|국장스캔|진입|매수)(?:@\S+)?(?:\s+.*)?$"),
            handle_tradingview_scan_command,
        )
    )
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/(?:변화|상태변화|전환|알림)(?:@\S+)?(?:\s+.*)?$"),
            handle_lazy_alpha_transition_command,
        )
    )
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/(?:추천|후보|추천후보)(?:@\S+)?(?:\s+.*)?$"),
            handle_recommendation_command,
        )
    )
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/(?:추천쿨다운|쿨다운)(?:@\S+)?(?:\s+.*)?$"),
            handle_recommendation_cooldown_command,
        )
    )
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/(?:선행|발굴)(?:@\S+)?(?:\s+.*)?$"),
            handle_leading_discovery_command,
        )
    )
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/(?:검증|백테스트)(?:@\S+)?(?:\s+.*)?$"),
            handle_backtest_command,
        )
    )
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/종목(?:@\S+)?(?:\s+.*)?$"),
            handle_korean_stock_command,
        )
    )
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    tg_app.add_handler(CallbackQueryHandler(handle_signal_console_callback, pattern="^sig:"))
    tg_app.add_handler(CallbackQueryHandler(handle_callback, pattern="^ticker:"))

    port = int(os.getenv("PORT", "8080"))
    assert_port_available("0.0.0.0", port)
    uv_config = uvicorn.Config(alert_app, host="0.0.0.0", port=port, log_level="info")
    uv_server = uvicorn.Server(uv_config)

    async with tg_app:
        await tg_app.start()
        await tg_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram polling 시작. Alert server port=%d", port)
        await uv_server.serve()  # SIGTERM까지 블록
        await tg_app.updater.stop()
        await tg_app.stop()


if __name__ == "__main__":
    asyncio.run(_run())
