"""API endpoints - Phase 3 (Final Repair with Depends)"""
import os
import time
import json
import logging
from typing import Optional, List

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    UnifiedResponse,
    EscalationRequest,
)
from app.models.database import (
    Conversation, 
    Message, 
    User, 
    EmotionHistory,
    get_db
)
from app.security import (
    InputSanitizer,
    PIIMasking,
    PromptInjectionDefense,
    RateLimiter,
    get_verifier,
    rbac,
)
from app.security.encryption import EncryptionService
from app.services.dst import DSTManager
from app.services.emotion import EmotionCategory, EmotionScore, EmotionTracker
from app.services.knowledge import HybridKnowledgeV7
from app.services.worker import AsyncMessageProcessor
from app.utils.logger import StructuredLogger

app = FastAPI(title="OmniBot API", version="1.0.0")

# Dependencies (initialized on startup)
sanitizer = InputSanitizer()
pii_masking = PIIMasking()
prompt_defense = PromptInjectionDefense()
rate_limiter = RateLimiter()
dst_manager = DSTManager()
encryption_service = EncryptionService()
logger = StructuredLogger("omnibot")

# Global worker
worker: Optional[AsyncMessageProcessor] = None

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
MESSENGER_APP_SECRET = os.getenv("MESSENGER_APP_SECRET", "messenger_secret")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "whatsapp_secret")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@app.on_event("startup")
async def startup_event():
    global worker
    try:
        worker = await AsyncMessageProcessor.create(REDIS_URL)
        logger.info("worker_started", redis_url=REDIS_URL)
    except Exception as e:
        logger.error("worker_start_failed", error=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    if worker:
        await worker.close()


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


async def get_active_conversation(db: AsyncSession, user: User) -> Conversation:
    """Helper to get or create an active conversation for a user"""
    stmt = select(Conversation).where(
        Conversation.unified_user_id == user.unified_user_id,
        Conversation.status == "active"
    ).order_by(desc(Conversation.started_at))
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    
    if not conv:
        conv = Conversation(
            unified_user_id=user.unified_user_id,
            platform=user.platform,
            status="active"
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
    return conv


async def get_emotion_tracker(db: AsyncSession, conversation_id: int) -> EmotionTracker:
    """Load emotion history and return a tracker"""
    stmt = select(EmotionHistory).where(EmotionHistory.conversation_id == conversation_id).order_by(desc(EmotionHistory.timestamp)).limit(10)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    
    history = [
        EmotionScore(
            category=EmotionCategory(row.category),
            intensity=row.intensity,
            timestamp=row.timestamp
        )
        for row in reversed(rows)
    ]
    return EmotionTracker(history=history)


def verify_signature(platform: str, body: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature"""
    verifier = get_verifier(platform, secret)
    if verifier:
        return verifier.verify(body, signature)
    return False


async def process_webhook_message(db: AsyncSession, platform: str, platform_user_id: str, text_content: str):
    """Generic message processing logic for all platforms"""
    # 1. Get user and active conversation
    user = await get_or_create_user(db, platform, platform_user_id)
    conv = await get_active_conversation(db, user)

    # 2. Sanitize and Security checks
    clean_text = sanitizer.sanitize(text_content)
    security_check = prompt_defense.check_input(clean_text)
    if not security_check.is_safe:
        logger.warn("prompt_injection_detected", platform=platform, reason=security_check.blocked_reason)
        return "Security violation detected", "blocked"

    # 3. PII masking
    mask_result = pii_masking.mask(clean_text)
    processed_text = mask_result.masked_text

    # 4. DST: Process Turn
    intent = "inquiry" if any(k in clean_text for k in ["詢問", "查詢", "什麼", "如何"]) else None
    state = dst_manager.process_turn(conv.id, intent, {"content": clean_text})
    
    # 5. Emotion Tracking
    sentiment = "negative" if any(k in clean_text for k in ["生氣", "爛", "慢", "不爽", "差"]) else "neutral"
    category = EmotionCategory.NEGATIVE if sentiment == "negative" else EmotionCategory.NEUTRAL
    
    # Save to DB
    db.add(EmotionHistory(
        conversation_id=conv.id,
        category=category.value,
        intensity=0.8
    ))
    
    # Load tracker with history
    tracker = await get_emotion_tracker(db, conv.id)
    tracker.add(EmotionScore(category=category, intensity=0.8))

    # 6. Response Logic
    if pii_masking.should_escalate(clean_text) or tracker.should_escalate():
        response_content = "正在為您轉接人工客服"
        knowledge_source = "escalate"
    else:
        # Query Hybrid Knowledge Layer (With LLM enabled for Phase 3)
        knowledge_layer = HybridKnowledgeV7(db, llm_client=True)
        result = await knowledge_layer.query(processed_text, user_context={"state": state.current_state.value})
        response_content = result.content
        knowledge_source = result.source

    # 7. Save Messages (with Encryption at rest for user content)
    encrypted_user_content = encryption_service.encrypt(processed_text)
    
    db.add(Message(
        conversation_id=conv.id,
        role="user",
        content=encrypted_user_content,
        intent_detected=state.primary_intent
    ))
    db.add(Message(
        conversation_id=conv.id,
        role="assistant",
        content=response_content,
        knowledge_source=knowledge_source
    ))
    
    # Update conversation state
    conv.dst_state = {"current": state.current_state.value, "turn": state.turn_count}
    
    # 8. Async Work (Produce to stream)
    if worker:
        await worker.produce("omnibot:analytics", {
            "conversation_id": str(conv.id),
            "platform": platform,
            "sentiment": sentiment,
            "knowledge_source": knowledge_source
        })

    return response_content, knowledge_source


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

    if not await rate_limiter.check("telegram", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if x_telegram_bot_api_secret and TELEGRAM_BOT_TOKEN:
        if not verify_signature("telegram", body, x_telegram_bot_api_secret, TELEGRAM_BOT_TOKEN):
            logger.warn("telegram_invalid_signature")

    data = await request.json()
    message_data = data.get("message", {})
    platform_user_id = str(message_data.get("from", {}).get("id", ""))
    text_content = message_data.get("text", "")

    response_content, _ = await process_webhook_message(db, "telegram", platform_user_id, text_content)
    
    await db.commit()
    return {"success": True, "data": {"response": response_content}}


@app.post("/api/v1/webhook/line")
async def line_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_line_signature: Optional[str] = Header(None)
):
    """LINE Messaging API webhook"""
    body = await request.body()

    if not await rate_limiter.check("line", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if x_line_signature and LINE_CHANNEL_SECRET:
        if not verify_signature("line", body, x_line_signature, LINE_CHANNEL_SECRET):
            logger.warn("line_invalid_signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    events = data.get("events", [])

    responses = []
    for event in events:
        if event.get("type") == "message":
            platform_user_id = event.get("source", {}).get("userId", "")
            text_content = event.get("message", {}).get("text", "")
            
            response_content, _ = await process_webhook_message(db, "line", platform_user_id, text_content)
            responses.append(response_content)

    await db.commit()
    return {"success": True, "data": {"responses": responses}}


@app.post("/api/v1/webhook/messenger")
async def messenger_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature: Optional[str] = Header(None)
):
    """Messenger webhook with signature verification"""
    body = await request.body()
    if not await rate_limiter.check("messenger", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if x_hub_signature and MESSENGER_APP_SECRET:
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
                response, _ = await process_webhook_message(db, "messenger", sender_id, text_content)
                responses.append(response)

    await db.commit()
    return {"success": True, "data": {"responses": responses}}


@app.post("/api/v1/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None)
):
    """WhatsApp webhook with signature verification"""
    body = await request.body()
    if not await rate_limiter.check("whatsapp", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if x_hub_signature_256 and WHATSAPP_APP_SECRET:
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
                response, _ = await process_webhook_message(db, "whatsapp", sender_id, text_content)
                results.append(response)

    await db.commit()
    return {"success": True, "data": {"responses": results}}


@app.get("/api/v1/knowledge")
async def query_knowledge(
    q: str,
    category: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    user_role: str = Depends(rbac.require("knowledge", "read"))
):
    """Query knowledge base"""
    return {"success": True, "data": {"items": [], "total": 0, "page": page, "limit": limit}}


@app.post("/api/v1/knowledge")
async def create_knowledge(
    item: dict,
    user_role: str = Depends(rbac.require("knowledge", "write"))
):
    """Create knowledge entry"""
    return {"success": True, "data": {"id": 1}}


@app.put("/api/v1/knowledge/{id}")
async def update_knowledge(
    id: int, 
    item: dict,
    user_role: str = Depends(rbac.require("knowledge", "write"))
):
    """Update knowledge entry"""
    return {"success": True, "data": {"id": id}}


@app.delete("/api/v1/knowledge/{id}")
async def delete_knowledge(
    id: int,
    user_role: str = Depends(rbac.require("knowledge", "delete"))
):
    """Delete knowledge entry"""
    return {"success": True, "data": {"deleted": True}}


@app.post("/api/v1/knowledge/bulk")
async def bulk_import(
    items: list,
    user_role: str = Depends(rbac.require("knowledge", "write"))
):
    """Bulk import knowledge"""
    return {"success": True, "data": {"imported": len(items)}}


@app.get("/api/v1/conversations")
async def list_conversations(
    page: int = 1,
    limit: int = 20,
    user_role: str = Depends(rbac.require("conversations", "read"))
):
    """List conversations"""
    return {"success": True, "data": {"items": [], "total": 0, "page": page, "limit": limit}}
