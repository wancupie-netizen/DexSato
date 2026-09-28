"""Feature-gated customer Telegram linking; independent of founder notifications."""

from __future__ import annotations

import hmac
import json
import os
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from application.product_auth_routes import product_auth_view
from application.product_auth_web import require_same_origin
from application.product_identity_runtime import build_telegram_link_service


router = APIRouter(include_in_schema=False)
_USERNAME = re.compile(r"[A-Za-z0-9_]{5,32}\Z")


def _configuration() -> tuple[str, str]:
    if os.getenv("DEXSATO_TELEGRAM_LINK_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(status_code=404, detail="Not found.")
    username = os.getenv("DEXSATO_TELEGRAM_BOT_USERNAME", "").lstrip("@")
    secret = os.getenv("DEXSATO_TELEGRAM_WEBHOOK_SECRET", "")
    if not _USERNAME.fullmatch(username) or not (32 <= len(secret) <= 256) or not re.fullmatch(r"[A-Za-z0-9_-]+", secret):
        raise HTTPException(status_code=503, detail="Telegram linking is unavailable.")
    return username, secret


@router.post("/auth/telegram/link")
async def begin_telegram_link(request: Request) -> JSONResponse:
    username, _ = _configuration()
    require_same_origin(request)
    principal = await run_in_threadpool(lambda: product_auth_view(request).principal)
    if not principal.authenticated or principal.user_id is None:
        raise HTTPException(status_code=401, detail="Sign in to link Telegram.")
    try:
        token = await run_in_threadpool(build_telegram_link_service().issue, user_id=principal.user_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Telegram linking is unavailable.") from error
    return JSONResponse(
        {"url": f"https://t.me/{username}?start={token}", "expires_in_seconds": 600},
        headers={"Cache-Control": "no-store"},
    )


@router.post("/telegram/link/webhook")
async def telegram_link_webhook(request: Request) -> JSONResponse:
    _, secret = _configuration()
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(supplied, secret):
        raise HTTPException(status_code=401, detail="Unauthorized.")
    body = await request.body()
    if len(body) > 8192:
        raise HTTPException(status_code=413, detail="Request too large.")
    try:
        update = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid update.") from None
    if not isinstance(update, dict):
        return JSONResponse({"ok": True})
    message = update.get("message")
    if not isinstance(message, dict):
        return JSONResponse({"ok": True})
    chat, sender, text = message.get("chat"), message.get("from"), message.get("text")
    if not isinstance(chat, dict) or not isinstance(sender, dict) or chat.get("type") != "private" or not isinstance(text, str):
        return JSONResponse({"ok": True})
    telegram_user_id, chat_id = sender.get("id"), chat.get("id")
    if type(telegram_user_id) is not int or type(chat_id) is not int or telegram_user_id <= 0 or chat_id != telegram_user_id:
        return JSONResponse({"ok": True})
    match = re.fullmatch(r"/start(?:@[A-Za-z0-9_]+)? ([A-Za-z0-9_-]{43})", text.strip())
    if not match:
        return JSONResponse({"ok": True})
    try:
        linked = await run_in_threadpool(
            build_telegram_link_service().redeem,
            token=match.group(1), telegram_user_id=telegram_user_id, chat_id=chat_id,
        )
    except Exception as error:
        raise HTTPException(status_code=503, detail="Telegram linking is unavailable.") from error
    # Telegram's webhook reply sends the confirmation without a separate bot API call.
    if linked:
        return JSONResponse({"method": "sendMessage", "chat_id": chat["id"], "text": "Telegram is linked to your DexSato account."})
    return JSONResponse({"ok": True})
