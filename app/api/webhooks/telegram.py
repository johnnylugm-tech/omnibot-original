"""Telegram webhook handler.

Phase 3 refactor: extracted from app/api/__init__.py
"""
import hashlib
import hmac
from typing import Any, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.api.core import process_webhook_message
from app.security import RateLimiter
from app.security.rbac import get_ip_whitelist
from app.security.signature import get_verifier
from app.utils.i18n import i18n
from app.utils.metrics import REQUEST_COUNT

router = APIRouter(prefix="/api/v1/webhook/telegram", tags=["telegram"])

TELEGRAM_BOT_TOKEN = "秘密"  # noqa: S105 — loaded from env in __init__.py
LINE_CHANNEL_SECRET = ""


def verify_telegram_signature(body: bytes, secret_token: str) -> bool:
    """Verify Telegram Bot API secret token using HMAC-SHA256."""
    if not secret_token:
        return True  # Skip verification if not configured
    secret = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).hexdigest()
    return hmac.compare_digest(secret, secret_token)


@router.post("")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_telegram_bot_api_secret_token: Optional[str] = Header(
        None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> Any:
    """Telegram bot webhook"""
    REQUEST_COUNT.labels(method="POST", endpoint="telegram", platform="telegram").inc()

    ip_whitelist = get_ip_whitelist()
    client_ip = ip_whitelist.get_client_ip(request)
    if not ip_whitelist.is_allowed(client_ip):
        return JSONResponse(status_code=403, content={})

    if not await RateLimiter().check("telegram", "user"):
        raise HTTPException(status_code=429, detail=i18n.translate("rate_limit"))

    if x_telegram_bot_api_secret_token:
        body = await request.body()
        if not verify_telegram_signature(body, x_telegram_bot_api_secret_token):
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Invalid signature"},
            )

    data = await request.json()
    message_data = data.get("message", {})
    platform_user_id = str(message_data.get("from", {}).get("id", ""))
    text_content = message_data.get("text", "")

    response_content, _ = await process_webhook_message(
        db, "telegram", platform_user_id, text_content
    )

    await db.commit()
    return {"success": True, "data": {"response": response_content}}
