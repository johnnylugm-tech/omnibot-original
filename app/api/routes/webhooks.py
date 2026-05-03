"""Webhook handlers for Telegram, LINE, Messenger, WhatsApp."""

import asyncio
import os
import time
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import (
    DAILY_COST_CAP,
    MESSENGER_APP_SECRET,
    WHATSAPP_APP_SECRET,
    degradation_manager,
)
from app.api.deps import (
    cost_model,
    dst_manager,
    encryption_service,
    ip_whitelist,
    logger,
    pii_masking,
    prompt_defense,
    rate_limiter,
    sanitizer,
)

# NOTE: helpers are imported lazily inside each handler to allow test-patching
# app.api.get_active_conversation / app.api.get_or_create_user.
# Do NOT move these to module level — it breaks @patch on those symbols.
from app.models.database import Conversation, EmotionHistory, Message, get_db
from app.security import get_verifier
from app.services.emotion import EmotionCategory, EmotionScore, EmotionTracker
from app.services.knowledge import HybridKnowledgeV7
from app.utils.i18n import i18n
from app.utils.metrics import LLM_TOKEN_USAGE, MESSAGE_SENTIMENT, REQUEST_LATENCY

router = APIRouter(prefix="/api/v1/webhook", tags=["webhooks"])

# Global worker reference — injected by the app lifespan
worker: Optional[Any] = None


def set_worker(w: Any) -> None:
    global worker
    global worker
    worker = w


# ── Signature verification ────────────────────────────────────────────────────


def verify_signature(platform: str, body: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature for a given platform."""
    verifier = get_verifier(platform, secret)
    if verifier:
        return verifier.verify(body, signature)
    return False


# ── Core message processor ───────────────────────────────────────────────────


async def process_webhook_message(
    db: AsyncSession,
    platform: str,
    platform_user_id: str,
    text_content: str,
    lang: str = "zh-TW",
) -> tuple[str, str]:
    """
    Generic message processing shared by all webhook handlers.

    Returns (response_content, knowledge_source).
    """
    from app.api.helpers import get_active_conversation, get_or_create_user
    from app.utils.tracing import tracer

    start_time = time.time()

    from sqlalchemy.exc import DBAPIError

    try:
        with tracer.start_as_current_span(f"process_{platform}_message") as span:
            span.set_attribute("platform", platform)
            span.set_attribute("user_id", platform_user_id)

            # 1. Get user and active conversation
            user = await get_or_create_user(db, platform, platform_user_id)
            conv = await get_active_conversation(db, user.unified_user_id, platform)

            # 2. Sanitize and Security checks
            clean_text = sanitizer.sanitize(text_content)
            security_check = prompt_defense.check_input(clean_text)
            if not security_check.is_safe:
                logger.warn(
                    "prompt_injection_detected",
                    platform=platform,
                    reason=security_check.blocked_reason,
                )
                return "Security violation detected", "blocked"

            # 3. PII masking
            mask_result = pii_masking.mask(clean_text)
            processed_text = mask_result.masked_text

            # 4. DST: Process Turn
            intent = (
                "inquiry"
                if any(k in clean_text for k in ["詢問", "查詢", "什麼", "如何"])
                else None
            )
            state = dst_manager.process_turn(
                int(conv.id), intent, {"content": clean_text}
            )

            # 5. Emotion Tracking
            sentiment = (
                "negative"
                if any(k in clean_text for k in ["生氣", "爛", "慢", "不爽", "差"])
                else "neutral"
            )
            category = (
                EmotionCategory.NEGATIVE
                if sentiment == "negative"
                else EmotionCategory.NEUTRAL
            )

            MESSAGE_SENTIMENT.labels(platform=platform).observe(
                0.1 if sentiment == "negative" else 0.8
            )

            db.add(
                EmotionHistory(
                    conversation_id=conv.id, category=category.value, intensity=0.8
                )
            )

            tracker = EmotionTracker()
            tracker.add(EmotionScore(category=category, intensity=0.8))

            # 6. Response Logic
            import app.api

            allowed_layers = app.api.degradation_manager.get_allowed_layers()

            if pii_masking.should_escalate(clean_text) or tracker.should_escalate():
                response_content = i18n.translate("escalate", lang)
                knowledge_source = "escalate"
            else:
                use_llm = allowed_layers.get("llm", True)
                knowledge_layer = HybridKnowledgeV7(db, llm_client=use_llm)

                try:
                    llm_start = time.time()
                    result = await knowledge_layer.query(
                        processed_text,
                        user_context={"state": state.current_state.value},
                    )
                    llm_duration = time.time() - llm_start

                    degradation_manager.update_metrics(
                        llm_latency=llm_duration, llm_success=True
                    )

                    response_content = result.content
                    knowledge_source = result.source

                    if knowledge_source == "llm":
                        LLM_TOKEN_USAGE.labels(
                            model="simulated", token_type="total"
                        ).inc(50)
                except (asyncio.TimeoutError, TimeoutError):
                    degradation_manager.update_metrics(llm_success=False)
                    raise
                except Exception as e:
                    logger.error("knowledge_query_failed", error=str(e))
                    degradation_manager.update_metrics(llm_success=False)
                    response_content = i18n.translate("error", lang)
                    knowledge_source = "error"

            # 7. Save Messages (with Encryption and Cost Model)
            encrypted_user_content = encryption_service.encrypt(processed_text)
            duration_ms = int((time.time() - start_time) * 1000)

            cost_map = {"rule": 0.001, "rag": 0.005, "llm": 0.02, "escalate": 0.05}
            raw_cost = cost_map.get(knowledge_source, 0.0)

            today = datetime.utcnow().date()
            daily_spend_stmt = (
                select(func.sum(Conversation.resolution_cost))
                .where(text("DATE(started_at) = :today"))
                .params(today=today)
            )
            try:
                daily_spend_result = await db.execute(daily_spend_stmt)
                current_daily_spend = float(daily_spend_result.scalar() or 0.0)
            except DBAPIError:
                await db.rollback()
                current_daily_spend = 0.0

            cost = cost_model.apply_daily_cap(
                current_daily_spend, raw_cost, cap=DAILY_COST_CAP
            )

            if cost < raw_cost:
                logger.warn(
                    "daily_cost_cap_exceeded", raw_cost=raw_cost, allowed_cost=cost
                )

            try:
                db.add(
                    Message(
                        conversation_id=conv.id,
                        role="user",
                        content=encrypted_user_content,
                        intent_detected=state.primary_intent,
                        duration_ms=duration_ms,
                    )
                )
                db.add(
                    Message(
                        conversation_id=conv.id,
                        role="assistant",
                        content=response_content,
                        knowledge_source=knowledge_source,
                        confidence=0.9 if knowledge_source != "llm" else 0.85,
                    )
                )

                conv.dst_state = {
                    "current": state.current_state.value,
                    "turn": state.turn_count,
                }
                conv.resolution_cost = float((conv.resolution_cost or 0.0) + cost)
                conv.response_time_ms = int((conv.response_time_ms or 0) + duration_ms)
                await db.flush()
            except DBAPIError:
                await db.rollback()
                logger.error("db_logging_failed_rolling_back")

            # 8. Async Work
            if worker:
                await worker.produce(
                    "omnibot:analytics",
                    {
                        "conversation_id": str(conv.id),
                        "platform": platform,
                        "sentiment": sentiment,
                        "knowledge_source": knowledge_source,
                        "cost": cost,
                    },
                )

            REQUEST_LATENCY.labels(endpoint=f"webhook_{platform}").observe(
                time.time() - start_time
            )
            return response_content, knowledge_source

    except DBAPIError as e:
        await db.rollback()
        logger.error("process_message_db_error", error=str(e))
        return i18n.translate("error", lang), "error"


# ── Telegram ─────────────────────────────────────────────────────────────────


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_telegram_bot_api_secret_token: Optional[str] = Header(
        None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> JSONResponse:
    """Telegram bot webhook"""
    from app.utils.metrics import REQUEST_COUNT

    REQUEST_COUNT.labels(method="POST", endpoint="telegram", platform="telegram").inc()
    body = await request.body()

    client_ip = ip_whitelist.get_client_ip(request)
    if not ip_whitelist.is_allowed(client_ip):
        logger.warn("telegram_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if not await rate_limiter.check("telegram", "user"):
        raise HTTPException(status_code=429, detail=i18n.translate("rate_limit"))

    is_testing = os.getenv("TESTING", "false").lower() == "true"
    import app.api

    if app.api.TELEGRAM_BOT_TOKEN and app.api.TELEGRAM_BOT_TOKEN != "":
        # In testing, allow missing signature, but if provided, it MUST be valid
        if not x_telegram_bot_api_secret_token:
            if is_testing:
                pass
            else:
                logger.warn("telegram_missing_signature")
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "error": "Missing signature"},
                )
        elif not verify_signature(
            "telegram",
            body,
            x_telegram_bot_api_secret_token,
            app.api.TELEGRAM_BOT_TOKEN,
        ):
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
    return JSONResponse(
        content={"success": True, "data": {"response": response_content}}
    )


# ── LINE ──────────────────────────────────────────────────────────────────────


@router.post("/line")
async def line_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_line_signature: Optional[str] = Header(None),
) -> JSONResponse:
    """LINE Messaging API webhook"""
    from app.utils.metrics import REQUEST_COUNT

    REQUEST_COUNT.labels(method="POST", endpoint="line", platform="line").inc()
    body = await request.body()

    client_ip = ip_whitelist.get_client_ip(request)
    if not ip_whitelist.is_allowed(client_ip):
        logger.warn("line_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if not await rate_limiter.check("line", "user"):
        raise HTTPException(status_code=429, detail=i18n.translate("rate_limit"))

    is_testing = os.getenv("TESTING", "false").lower() == "true"
    import app.api

    if app.api.LINE_CHANNEL_SECRET and app.api.LINE_CHANNEL_SECRET != "":
        # In testing, allow missing signature, but if provided, it MUST be valid
        if not x_line_signature:
            if is_testing:
                pass
            else:
                logger.warn("line_missing_signature")
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "error": "Missing signature"},
                )
        elif not verify_signature(
            "line", body, x_line_signature, app.api.LINE_CHANNEL_SECRET
        ):
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
    return JSONResponse(content={"success": True, "data": {"responses": responses}})


# ── Messenger ─────────────────────────────────────────────────────────────────


@router.post("/messenger")
async def messenger_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature: Optional[str] = Header(None),
) -> JSONResponse:
    """Messenger webhook with signature verification"""
    from app.utils.metrics import REQUEST_COUNT

    REQUEST_COUNT.labels(
        method="POST", endpoint="messenger", platform="messenger"
    ).inc()
    body = await request.body()

    client_ip = ip_whitelist.get_client_ip(request)
    if not ip_whitelist.is_allowed(client_ip):
        logger.warn("messenger_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if not await rate_limiter.check("messenger", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if x_hub_signature and MESSENGER_APP_SECRET:
        if not verify_signature(
            "messenger", body, x_hub_signature, MESSENGER_APP_SECRET
        ):
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
                response_content, _ = await process_webhook_message(
                    db, "messenger", sender_id, text_content
                )
                responses.append(response_content)

    await db.commit()
    return JSONResponse(content={"success": True, "data": {"responses": responses}})


# ── WhatsApp ──────────────────────────────────────────────────────────────────


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None),
) -> JSONResponse:
    """WhatsApp webhook with signature verification"""
    from app.utils.metrics import REQUEST_COUNT

    REQUEST_COUNT.labels(method="POST", endpoint="whatsapp", platform="whatsapp").inc()
    body = await request.body()

    client_ip = ip_whitelist.get_client_ip(request)
    if not ip_whitelist.is_allowed(client_ip):
        logger.warn("whatsapp_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if not await rate_limiter.check("whatsapp", "user"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if x_hub_signature_256 and WHATSAPP_APP_SECRET:
        if not verify_signature(
            "whatsapp", body, x_hub_signature_256, WHATSAPP_APP_SECRET
        ):
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
                response_content, _ = await process_webhook_message(
                    db, "whatsapp", sender_id, text_content
                )
                results.append(response_content)

    await db.commit()
    return JSONResponse(content={"success": True, "data": results})
