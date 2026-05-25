"""bot.py — 04_stock_intel Telegram 봇 진입점.

종목명 입력 → search_ticker → 4개 data 모듈 조회 → 포맷 → 전송.
data/ 모듈은 모두 동기 함수 → asyncio.to_thread()로 래핑.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
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
from utils.formatter import format_message
from utils.ticker import refresh_ticker_cache, search_ticker

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
TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

ALLOWED_IDS: set[int] = {
    int(x.strip())
    for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",")
    if x.strip()
}

# 02_audit_safe_signals feed 연동 (설정 안 하면 /feed 비활성)
_SIGNALS_URL: str = os.getenv("ASS_SIGNALS_URL", "")   # e.g. https://audit-safe-signals.fly.dev/signals
_SIGNALS_SECRET: str = os.getenv("ASS_SIGNALS_SECRET", "")
_KST = ZoneInfo("Asia/Seoul")

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
    supply, short_sell, technical, fundamental, audit = await asyncio.to_thread(
        fetch_all,
        ticker,
    )
    text = format_message(
        name,
        ticker,
        supply,
        short_sell,
        technical,
        fundamental,
        audit,
    )
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


async def handle_start(update: Update, context) -> None:
    """/start 커맨드 핸들러."""
    if not await check_allowed(update):
        return

    await update.message.reply_text(
        "종목명을 입력하면 수급현황, 공매도, 기술적 지표, 펀더멘탈, 감사법인을 보여드립니다.\n"
        "DM: 삼성전자 / SK하이닉스 / NAVER\n"
        "그룹: /s 삼성전자 또는 /stock 삼성전자\n\n"
        "/feed — 최근 BUY 시그널 목록\n"
        "/feed 50 — 최근 50건"
    )


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
    await _lookup_and_reply(update, query)


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
    supply, short_sell, technical, fundamental, audit = await asyncio.to_thread(
        fetch_all,
        ticker,
    )
    text = format_message(
        name,
        ticker,
        supply,
        short_sell,
        technical,
        fundamental,
        audit,
    )
    await query.edit_message_text(text)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
async def post_init(application: Application) -> None:
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
    tg_app.add_handler(CommandHandler(["stock", "s", "check"], handle_lookup_command))
    tg_app.add_handler(
        MessageHandler(
            filters.Regex(r"^/조회(?:@\S+)?(?:\s+.*)?$"),
            handle_korean_lookup_text,
        )
    )
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    tg_app.add_handler(CallbackQueryHandler(handle_callback, pattern="^ticker:"))

    port = int(os.getenv("PORT", "8080"))
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
