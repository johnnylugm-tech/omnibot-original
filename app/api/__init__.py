"""API endpoints - Phase 3"""
import os
import time
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    UnifiedResponse,
)
from app.models.database import Message, User, get_db
from app.security import (
    InputSanitizer,
    PIIMasking,
    PromptInjectionDefense,
    RateLimiter,
    get_verifier,
    rbac,
)
from app.services.dst import DSTManager
from app.services.emotion import EmotionScore, EmotionTracker
from app.services.knowledge import HybridKnowledgeV7
from app.utils.logger import StructuredLogger

app = FastAPI(title="OmniBot API", version="1.0.0")

# Dependencies (initialized on startup)
sanitizer = InputSanitizer()
pii_masking = PIIMasking()
prompt_defense = PromptInjectionDefense()
rate_limiter = RateLimiter()
dst_manager = DSTManager()
logger = StructuredLogger("omnibot")

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )


async def get_or_create_user(db: AsyncSession, platform: str, platform_user_id: str) -> User:
    """Helper to get or create a user across platforms"""
    stmt = select(User).where(User.platform == platform, User.platform_user_id == platform_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(platform=platform, platform_user_id=platform_user_id)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


def verify_signature(platform: str, body: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature"""
    verifier = get_verifier(platform, secret)
    if verifier:
        return verifier.verify(body, signature)
    return False


@app.get("/api/v1/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint with DB and Redis monitoring"""
    postgres_ok = False
    redis_ok = False
    
    try:
        await db.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception as e:
        logger.error("health_check_postgres_failed", error=str(e))

    try:
        redis_client = await aioredis.from_url(REDIS_URL)
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
        "uptime_seconds": time.time()
    }


@app.post("/api/v1/webhook/telegram")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_telegram_bot_api_secret: Optional[str] = Header(None)
):
    """Telegram bot webhook"""
    body = await request.body()

    # Rate limit check
    if not rate_limiter.check("telegram", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Signature verification
    if x_telegram_bot_api_secret and TELEGRAM_BOT_TOKEN:
        if not verify_signature("telegram", body, x_telegram_bot_api_secret, TELEGRAM_BOT_TOKEN):
            logger.warn("telegram_invalid_signature")

    data = await request.json()
    message_data = data.get("message", {})
    platform_user_id = str(message_data.get("from", {}).get("id", ""))
    text_content = message_data.get("text", "")

    # Get user
    await get_or_create_user(db, "telegram", platform_user_id)

    # Sanitize input
    text_content = sanitizer.sanitize(text_content)

    # Prompt Injection Check (L3 - Phase 2)
    security_check = prompt_defense.check_input(text_content)
    if not security_check.is_safe:
        logger.warn("prompt_injection_detected", reason=security_check.blocked_reason)
        return JSONResponse(
            content={"success": False, "error": "Security violation detected"},
            status_code=400
        )

    # PII masking
    mask_result = pii_masking.mask(text_content)
    processed_text = mask_result.masked_text
    
    # Save user message
    db.add(Message(role="user", content=processed_text))

    if pii_masking.should_escalate(text_content):
        response_content = "正在為您轉接人工客服"
        knowledge_source = "escalate"
    else:
        # Query Hybrid Knowledge Layer
        knowledge_layer = HybridKnowledgeV7(db)
        result = await knowledge_layer.query(text_content)
        response_content = result.content
        knowledge_source = result.source

    # Save assistant message
    db.add(Message(role="assistant", content=response_content, knowledge_source=knowledge_source))
    await db.commit()

    logger.info("telegram_message", user_id=platform_user_id, source=knowledge_source)
    return {"success": True, "data": {"response": response_content}}


@app.post("/api/v1/webhook/line")
async def line_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_line_signature: Optional[str] = Header(None)
):
    """LINE Messaging API webhook"""
    body = await request.body()

    if not rate_limiter.check("line", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Signature verification
    if x_line_signature and LINE_CHANNEL_SECRET:
        if not verify_signature("line", body, x_line_signature, LINE_CHANNEL_SECRET):
            logger.warn("line_invalid_signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    events = data.get("events", [])

    responses = []
    knowledge_layer = HybridKnowledgeV7(db)
    
    for event in events:
        if event.get("type") == "message":
            platform_user_id = event.get("source", {}).get("userId", "")
            text_content = event.get("message", {}).get("text", "")
            
            await get_or_create_user(db, "line", platform_user_id)
            text_content = sanitizer.sanitize(text_content)
            
            # Security checks
            security_check = prompt_defense.check_input(text_content)
            if not security_check.is_safe:
                responses.append("Security violation detected")
                continue

            mask_result = pii_masking.mask(text_content)
            processed_text = mask_result.masked_text

            db.add(Message(role="user", content=processed_text))
            result = await knowledge_layer.query(text_content)
            db.add(Message(role="assistant", content=result.content, knowledge_source=result.source))
            responses.append(result.content)

    await db.commit()
    return {"success": True, "data": {"responses": responses}}


@app.get("/api/v1/knowledge")
async def query_knowledge(
    q: str,
    category: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    """Query knowledge base"""
    return {"success": True, "data": {"items": [], "total": 0, "page": page, "limit": limit}}


@app.post("/api/v1/knowledge")
@rbac.require("knowledge", "write")
async def create_knowledge(request: Request, item: dict):
    """Create knowledge entry"""
    return {"success": True, "data": {"id": 1}}


@app.put("/api/v1/knowledge/{id}")
@rbac.require("knowledge", "write")
async def update_knowledge(request: Request, id: int, item: dict):
    """Update knowledge entry"""
    return {"success": True, "data": {"id": id}}


@app.delete("/api/v1/knowledge/{id}")
@rbac.require("knowledge", "delete")
async def delete_knowledge(request: Request, id: int):
    """Delete knowledge entry"""
    return {"success": True, "data": {"deleted": True}}


@app.post("/api/v1/knowledge/bulk")
@rbac.require("knowledge", "write")
async def bulk_import(request: Request, items: list):
    """Bulk import knowledge"""
    return {"success": True, "data": {"imported": len(items)}}


@app.get("/api/v1/conversations")
async def list_conversations(
    page: int = 1,
    limit: int = 20
):
    """List conversations"""
    return {"success": True, "data": {"items": [], "total": 0, "page": page, "limit": limit}}
