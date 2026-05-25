"""Telegram Bot API sender for signal alerts."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def send_telegram_message(bot_token: str, chat_ids: list[int], text: str) -> bool:
    if not bot_token or not chat_ids:
        logger.warning("telegram not configured; skipping signal alert")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)]
    async with httpx.AsyncClient(timeout=10.0) as client:
        for chat_id in chat_ids:
            for chunk in chunks:
                response = await client.post(url, json={"chat_id": chat_id, "text": chunk})
                response.raise_for_status()
    return True

