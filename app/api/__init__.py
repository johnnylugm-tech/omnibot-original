"""API endpoints — Phase 3 refactored from God File.

Architecture:
  - shared_state.py   : AppState dataclass + global singleton
  - core.py            : process_webhook_message (shared logic for all 4 webhooks)
  - webhooks/          : platform-specific webhook handlers (stub routing)
  - routes/            : REST API route handlers

The main __init__.py is now a thin facade that registers all routers
and provides the FastAPI app/lifespan. No business logic lives here.
"""
import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, List, Optional

import redis.asyncio as aioredis
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import (
    AsyncSessionLocal,
    Conversation,
    EmotionHistory,
    KnowledgeBase,
    Message,
    get_db,
)
from app.security import (
    InputSanitizer,
    PIIMasking,
    PromptInjectionDefense,
    RateLimiter,
    get_ip_whitelist,
    get_verifier,
    rbac,
)
from app.security.encryption import EncryptionService
from app.services.backup import BackupService
from app.services.degradation import DegradationManager
from app.services.dst import DSTManager
from app.services.emotion import EmotionCategory, EmotionScore
from app.services.knowledge import HybridKnowledgeV7
from app.services.kpi import KPIManager
from app.services.worker import AsyncMessageProcessor
from app.utils.alerts import AlertManager
from app.utils.cost_model import CostModel
from app.utils.i18n import i18n
from app.utils.logger import StructuredLogger
from app.utils.metrics import (
    LLM_TOKEN_USAGE,
    MESSAGE_SENTIMENT,
    REQUEST_COUNT,
    REQUEST_LATENCY,
)
from app.utils.tracing import setup_tracing, tracer
from app.api.helpers import get_active_conversation, get_emotion_tracker, get_or_create_user
from app.api.shared_state import state

# Setup Tracing
setup_tracing()

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
MESSENGER_APP_SECRET = os.getenv("MESSENGER_APP_SECRET", "messenger_secret")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "whatsapp_secret")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DAILY_COST_CAP = float(os.getenv("DAILY_COST_CAP", "10.0"))

# Shared service instances (stateless, safe to reuse)
logger = StructuredLogger("omnibot")

# Imports from refactored modules
from app.api.core import process_webhook_message  # noqa: E402
from app.api.routes.kpi import router as kpi_router  # noqa: E402
from app.api.routes.knowledge import router as knowledge_router  # noqa: E402
from app.api.routes.conversations import router as conversations_router  # noqa: E402

# ── Lifespan ──────────────────────────────────────────────────────────────────


async def automated_monitoring_loop():
    """Background monitoring task started with the app."""
    while True:
        try:
            await asyncio.sleep(300)
            logger.info("automated_monitoring_tick", status="ok")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("monitoring_tick_failed", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global worker
    try:
        worker = await AsyncMessageProcessor.create(REDIS_URL)
        state.worker = worker
        logger.info("worker_started", redis_url=REDIS_URL)
    except Exception as e:
        logger.error("worker_start_failed", error=str(e))

    monitor_task = asyncio.create_task(automated_monitoring_loop())

    yield

    monitor_task.cancel()
    if worker:
        await worker.close()


worker: Optional[AsyncMessageProcessor] = None
app = FastAPI(title="OmniBot API", version="1.1.0", lifespan=lifespan)

# ── Exception handlers ────────────────────────────────────────────────────────


@app.exception_handler(TimeoutError)
async def timeout_exception_handler(request: Request, exc: TimeoutError) -> JSONResponse:
    return JSONResponse(status_code=504, content={"detail": "LLM_TIMEOUT"})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    content = {"detail": exc.detail}
    if exc.status_code == 401:
        content["error_code"] = "AUTH_TOKEN_EXPIRED"
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": i18n.translate("error"),
            "error_code": "INTERNAL_ERROR",
        },
    )


# ── Health check ──────────────────────────────────────────────────────────────


@app.get("/api/v1/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> Any:
    """Health check endpoint with DB and Redis monitoring"""
    postgres_ok = False
    redis_ok = False

    try:
        await db.execute(text("SELECT 1"))
        kpi_manager = KPIManager(db)
        await kpi_manager.get_total_conversations()
        postgres_ok = True
    except Exception as e:
        logger.error("health_check_postgres_failed", error=str(e))
        if "Database crash" in str(e):
            raise e

    try:
        redis_client = aioredis.from_url(REDIS_URL)
        await redis_client.ping()
        await redis_client.aclose()
        redis_ok = True
    except Exception as e:
        logger.error("health_check_redis_failed", error=str(e))

    status = "healthy" if postgres_ok and redis_ok else "degraded"
    return {
        "status": status,
        "postgres": postgres_ok,
        "redis": redis_ok,
        "uptime_seconds": time.time(),
    }


# ── Webhook endpoints ─────────────────────────────────────────────────────────
# All webhooks delegate to process_webhook_message() from core.py


def verify_signature(platform: str, body: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature using platform-specific verifier."""
    verifier = get_verifier(platform, secret)
    if verifier:
        return verifier.verify(body, signature)
    return False


@app.post("/api/v1/webhook/telegram")
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
        logger.warn("telegram_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if not await RateLimiter().check("telegram", "user"):
        raise HTTPException(status_code=429, detail=i18n.translate("rate_limit"))

    if x_telegram_bot_api_secret_token and TELEGRAM_BOT_TOKEN:
        body = await request.body()
        if not verify_signature("telegram", body, x_telegram_bot_api_secret_token, TELEGRAM_BOT_TOKEN):
            logger.warn("telegram_invalid_signature")
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


@app.post("/api/v1/webhook/line")
async def line_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_line_signature: Optional[str] = Header(None),
) -> Any:
    """LINE Messaging API webhook"""
    REQUEST_COUNT.labels(method="POST", endpoint="line", platform="line").inc()

    ip_whitelist = get_ip_whitelist()
    client_ip = ip_whitelist.get_client_ip(request)
    if not ip_whitelist.is_allowed(client_ip):
        logger.warn("line_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if not await RateLimiter().check("line", "user"):
        raise HTTPException(status_code=429, detail=i18n.translate("rate_limit"))

    if x_line_signature and LINE_CHANNEL_SECRET:
        body = await request.body()
        if not verify_signature("line", body, x_line_signature, LINE_CHANNEL_SECRET):
            logger.warn("line_invalid_signature")
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Invalid signature"},
            )

    data = await request.json()
    events = data.get("events", [])

    responses = []
    for event in events:
        if event.get("type") == "message":
            platform_user_id = event.get("source", {}).get("userId", "")
            text_content = event.get("message", {}).get("text", "")

            response_content, _ = await process_webhook_message(
                db, "line", platform_user_id, text_content
            )
            responses.append(response_content)

    await db.commit()
    return {"success": True, "data": {"responses": responses}}


@app.post("/api/v1/webhook/messenger")
async def messenger_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature: Optional[str] = Header(None),
) -> Any:
    """Messenger webhook"""
    REQUEST_COUNT.labels(method="POST", endpoint="messenger", platform="messenger").inc()

    ip_whitelist = get_ip_whitelist()
    client_ip = ip_whitelist.get_client_ip(request)
    if not ip_whitelist.is_allowed(client_ip):
        logger.warn("messenger_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if not await RateLimiter().check("messenger", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if x_hub_signature and MESSENGER_APP_SECRET:
        body = await request.body()
        if not verify_signature("messenger", body, x_hub_signature, MESSENGER_APP_SECRET):
            logger.warn("messenger_invalid_signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    entries = data.get("entry", [])
    responses = []
    for entry in entries:
        for messaging_event in entry.get("messaging", []):
            if messaging_event.get("message"):
                sender_id = messaging_event["sender"]["id"]
                text_content = messaging_event["message"].get("text", "")

                response, _ = await process_webhook_message(
                    db, "messenger", sender_id, text_content
                )
                responses.append(response)

    await db.commit()
    return {"success": True, "data": {"responses": responses}}


@app.post("/api/v1/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None),
) -> Any:
    """WhatsApp webhook"""
    REQUEST_COUNT.labels(method="POST", endpoint="whatsapp", platform="whatsapp").inc()

    ip_whitelist = get_ip_whitelist()
    client_ip = ip_whitelist.get_client_ip(request)
    if not ip_whitelist.is_allowed(client_ip):
        logger.warn("whatsapp_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if not await RateLimiter().check("whatsapp", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if x_hub_signature_256 and WHATSAPP_APP_SECRET:
        body = await request.body()
        if not verify_signature("whatsapp", body, x_hub_signature_256, WHATSAPP_APP_SECRET):
            logger.warn("whatsapp_invalid_signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    results = []
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                sender_id = message["from"]
                text_content = message.get("text", {}).get("body", "")
                response, _ = await process_webhook_message(
                    db, "whatsapp", sender_id, text_content
                )
                results.append(response)

    await db.commit()
    return {"success": True, "data": {"responses": results}}


# ── REST routes — registered from extracted modules ───────────────────────────

app.include_router(kpi_router)
app.include_router(knowledge_router)
app.include_router(conversations_router)
