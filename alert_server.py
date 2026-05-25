"""alert_server.py — 02_audit_safe_signals → push-alert HTTP endpoint.

POST /alert?secret=<ALERT_SECRET>
  body: {ticker, name, type, price, score, conviction, exchange, timeframe}
  → fetch_all(ticker) + Telegram push to ALERT_CHAT_IDS

GET /healthz → {"status": "ok"}
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel

from data.audit_firm import fetch_audit_firm
from data.fundamental import fetch_fundamental
from data.short_sell import fetch_short_sell
from data.supply import fetch_supply
from data.technical import fetch_technical
from signals.payload import TradingViewSignal
from signals.pipeline import SignalPipeline
from signals.storage import SignalStore
from signals.telegram import send_telegram_message
from utils.formatter import format_message

logger = logging.getLogger(__name__)

_ALERT_SECRET: str = os.environ.get("ALERT_SECRET", "")
_WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")
_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_ALERT_CHAT_IDS: list[int] = [
    int(x.strip())
    for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",")
    if x.strip()
]
_SIGNAL_CHAT_IDS: list[int] = [
    int(x.strip())
    for x in os.getenv("SIGNAL_CHAT_IDS", os.getenv("ALLOWED_CHAT_IDS", "")).split(",")
    if x.strip()
]
_STATE_DB_PATH: str = os.environ.get("STATE_DB_PATH", "./state.db")

app = FastAPI(title="stock-intel-alert", version="0.1.0")


class AlertPayload(BaseModel):
    ticker: str
    name: str
    type: str
    price: float
    score: int
    conviction: str
    exchange: str = ""
    timeframe: str = ""


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/webhook/tradingview")
async def handle_tradingview_webhook(
    request: Request,
    background: BackgroundTasks,
    secret: str = Query(default=""),
) -> dict:
    if _WEBHOOK_SECRET and not secrets.compare_digest(secret, _WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="invalid secret")
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid json: {exc!r}") from exc

    try:
        signal = TradingViewSignal.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"schema: {exc!r}") from exc

    background.add_task(_handle_tradingview_payload, payload)
    return {"received": True, "ticker": signal.ticker}


@app.post("/alert")
async def handle_alert(
    payload: AlertPayload,
    secret: str = Query(default=""),
) -> dict:
    if _ALERT_SECRET and not secrets.compare_digest(secret, _ALERT_SECRET):
        raise HTTPException(status_code=401, detail="invalid secret")

    supply, short_sell, technical, fundamental, audit = await asyncio.to_thread(
        _fetch_all, payload.ticker
    )

    header = (
        f"🔔 BUY 시그널 — {payload.name} ({payload.ticker})\n"
        f"   {payload.type}  |  Score {payload.score}  |  Conviction {payload.conviction}\n"
        f"   진입가 {payload.price:,.0f}원\n"
        f"───────────────────────────────\n"
    )
    body = format_message(
        payload.name,
        payload.ticker,
        supply,
        short_sell,
        technical,
        fundamental,
        audit,
    )
    text = header + body

    await _send_to_telegram(text)
    logger.info("alert pushed: ticker=%s chat_count=%d", payload.ticker, len(_ALERT_CHAT_IDS))
    return {"sent": True, "ticker": payload.ticker, "chat_count": len(_ALERT_CHAT_IDS)}


def _fetch_all(ticker: str) -> tuple[dict, dict, dict, dict, dict]:
    return (
        fetch_supply(ticker),
        fetch_short_sell(ticker),
        fetch_technical(ticker),
        fetch_fundamental(ticker),
        fetch_audit_firm(ticker),
    )


async def _handle_tradingview_payload(payload: dict) -> None:
    pipeline = getattr(app.state, "signal_pipeline", None)
    if pipeline is None:
        pipeline = _build_signal_pipeline()
        app.state.signal_pipeline = pipeline
    try:
        await pipeline.handle_payload(payload)
    except Exception:
        logger.exception("tradingview signal pipeline failed")


def _build_signal_pipeline() -> SignalPipeline:
    async def sender(text: str) -> bool:
        return await send_telegram_message(_BOT_TOKEN, _SIGNAL_CHAT_IDS, text)

    return SignalPipeline(
        store=SignalStore(_STATE_DB_PATH),
        audit_lookup=fetch_audit_firm,
        send_message=sender,
    )


async def _send_to_telegram(text: str) -> None:
    if not _BOT_TOKEN or not _ALERT_CHAT_IDS:
        logger.warning("telegram not configured — skipping send (BOT_TOKEN or ALLOWED_CHAT_IDS missing)")
        return

    url = f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
    # keep chunks under 4096 byte hard limit
    chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)]

    async with httpx.AsyncClient(timeout=10.0) as client:
        for chat_id in _ALERT_CHAT_IDS:
            for chunk in chunks:
                try:
                    r = await client.post(url, json={"chat_id": chat_id, "text": chunk})
                    r.raise_for_status()
                except Exception:
                    logger.exception("telegram send failed: chat_id=%s", chat_id)
