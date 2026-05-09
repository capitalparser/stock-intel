"""bot.py — 04_stock_intel Telegram 봇 진입점.

종목명 입력 → search_ticker → 4개 data 모듈 조회 → 포맷 → 전송.
data/ 모듈은 모두 동기 함수 → asyncio.to_thread()로 래핑.
"""
from __future__ import annotations

import asyncio
import logging
import os

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
def fetch_all(ticker: str) -> tuple[dict, dict, dict, dict]:
    """4개 data 모듈 직렬 호출. asyncio.to_thread에서 실행."""
    supply = fetch_supply(ticker)
    short_sell = fetch_short_sell(ticker)
    technical = fetch_technical(ticker)
    audit = fetch_audit_firm(ticker)
    return supply, short_sell, technical, audit


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
    supply, short_sell, technical, audit = await asyncio.to_thread(fetch_all, ticker)
    text = format_message(name, ticker, supply, short_sell, technical, audit)
    await loading_message.edit_text(text)


# ---------------------------------------------------------------------------
# 핸들러
# ---------------------------------------------------------------------------
async def handle_start(update: Update, context) -> None:
    """/start 커맨드 핸들러."""
    if not await check_allowed(update):
        return

    await update.message.reply_text(
        "안녕하세요! 종목명을 입력하면 수급현황, 공매도, 기술적 지표, 감사법인 정보를 보여드립니다.\n"
        "예) 삼성전자 / SK하이닉스 / NAVER"
    )


async def handle_text(update: Update, context) -> None:
    """텍스트 메시지 핸들러: 종목명 입력 → 검색 → 결과 분기."""
    if not await check_allowed(update):
        return

    query = update.message.text.strip()
    if not query:
        return

    results = await asyncio.to_thread(search_ticker, query)

    if not results:
        await update.message.reply_text("종목을 찾을 수 없습니다.")
        return

    if len(results) == 1:
        # 결과 1개: 바로 fetch_all + 포맷 + 전송
        item = results[0]
        loading_msg = await update.message.reply_text("🔍 조회 중...")
        await _fetch_and_reply(update, item["code"], item["name"], loading_msg)
        return

    # 결과 2~5개: InlineKeyboard로 선택지 표시
    buttons = [
        InlineKeyboardButton(
            f"{item['name']} ({item['market']})",
            callback_data=f"ticker:{item['code']}:{item['name']}",
        )
        for item in results[:5]
    ]
    keyboard = InlineKeyboardMarkup([[btn] for btn in buttons])
    await update.message.reply_text("종목을 선택해 주세요:", reply_markup=keyboard)


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
    supply, short_sell, technical, audit = await asyncio.to_thread(fetch_all, ticker)
    text = format_message(name, ticker, supply, short_sell, technical, audit)
    await query.edit_message_text(text)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
async def post_init(application: Application) -> None:
    scheduler.start()
    logger.info("봇 시작. 종목 캐시 갱신 스케줄: 매일 07:00 KST")


if __name__ == "__main__":
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^ticker:"))

    app.run_polling(allowed_updates=Update.ALL_TYPES)
