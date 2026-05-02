"""API endpoints - Phase 3 (Ultimate Production Ready) — refactored with lifespan DI"""
import os
import time
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Any, AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from sqlalchemy import text, select, desc, or_, func
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
    KnowledgeBase,
    get_db,
    AsyncSessionLocal,
)
from app.security import (
    InputSanitizer,
    PIIMasking,
    PromptInjectionDefense,
    RateLimiter,
    get_verifier,
    rbac,
    get_ip_whitelist,
)
from app.security.encryption import EncryptionService
from app.services.degradation import DegradationManager
from app.services.dst import DSTManager
from app.services.emotion import EmotionCategory, EmotionScore, EmotionTracker
from app.services.knowledge import HybridKnowledgeV7
from app.services.worker import AsyncMessageProcessor
from app.services.backup import BackupService
from app.utils.alerts import AlertManager
from app.utils.cost_model import CostModel
from app.utils.logger import StructuredLogger
from app.utils.metrics import REQUEST_COUNT, REQUEST_LATENCY, MESSAGE_SENTIMENT, LLM_TOKEN_USAGE
from app.utils.i18n import i18n

from app.utils.tracing import tracer, setup_tracing
from app.services.kpi import KPIManager

# Setup Tracing — only runs once at import time (cheap, stateless)
setup_tracing()

# ---------------------------------------------------------------------------
# AppState — holds all service singletons, managed by lifespan
# ---------------------------------------------------------------------------
class AppState:
    """Container for all application-wide service singletons."""

    def __init__(self) -> None:
        self.sanitizer: Optional[InputSanitizer] = None
        self.pii_masking: Optional[PIIMasking] = None
        self.prompt_defense: Optional[PromptInjectionDefense] = None
        self.rate_limiter: Optional[RateLimiter] = None
        self.ip_whitelist: Optional[Any] = None
        self.dst_manager: Optional[DSTManager] = None
        self.degradation_manager: Optional[DegradationManager] = None
        self.encryption_service: Optional[EncryptionService] = None
        self.alert_manager: Optional[AlertManager] = None
        self.cost_model: Optional[CostModel] = None
        self.backup_service: Optional[BackupService] = None
        self.worker: Optional[AsyncMessageProcessor] = None
        self.logger: Optional[StructuredLogger] = None

    async def init(self) -> None:
        """Initialize all services. Called once at startup."""
        self.logger = StructuredLogger("omnibot")
        self.sanitizer = InputSanitizer()
        self.pii_masking = PIIMasking()
        self.prompt_defense = PromptInjectionDefense()
        self.rate_limiter = RateLimiter()
        self.ip_whitelist = get_ip_whitelist()
        self.dst_manager = DSTManager()
        self.degradation_manager = DegradationManager()
        self.encryption_service = EncryptionService()
        self.alert_manager = AlertManager()
        self.cost_model = CostModel()
        self.backup_service = BackupService()

        # Worker needs async init
        try:
            self.worker = await AsyncMessageProcessor.create(REDIS_URL)
            self.logger.info("worker_started", redis_url=REDIS_URL)
        except Exception as e:
            self.logger.error("worker_start_failed", error=str(e))

        self.logger.info("app_state_initialized")

    async def shutdown(self) -> None:
        """Cleanup. Called once at shutdown."""
        if self.worker:
            await self.worker.close()
        self.logger.info("app_state_shutdown")


# ---------------------------------------------------------------------------
# FastAPI lifespan — replaces module-level singletons
# ---------------------------------------------------------------------------
_state: Optional[AppState] = None


def get_state() -> AppState:
    """FastAPI dependency that returns the shared AppState."""
    if _state is None:
        raise RuntimeError("AppState not initialized — app must be started via uvicorn")
    return _state


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage AppState lifecycle: init on startup, cleanup on shutdown."""
    global _state
    _state = AppState()
    await _state.init()

    # Start background monitoring
    monitor_task = asyncio.create_task(automated_monitoring_loop(_state))

    yield

    monitor_task.cancel()
    await _state.shutdown()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="OmniBot API", version="1.1.1", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Environment variables (keep at module level — they're just env reads)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
MESSENGER_APP_SECRET = os.getenv("MESSENGER_APP_SECRET", "messenger_secret")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "whatsapp_secret")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DAILY_COST_CAP = float(os.getenv("DAILY_COST_CAP", "50.0"))


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
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
    state = get_state()
    state.logger.error("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": i18n.translate("error"), "error_code": "INTERNAL_ERROR"},
    )


# ---------------------------------------------------------------------------
# Background monitoring loop
# ---------------------------------------------------------------------------
async def automated_monitoring_loop(state: AppState) -> None:
    """Background task for automated SLA and error monitoring."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                kpi = KPIManager(db)
                from app.services.escalation import EscalationManager
                esc_manager = EscalationManager(db)
                breaches = await esc_manager.get_sla_breaches()
                if breaches:
                    await state.alert_manager.check_sla_breach(len(breaches))
            await asyncio.sleep(60)
        except Exception as e:
            state.logger.error("monitoring_loop_error", error=str(e))
            await asyncio.sleep(60)


# ---------------------------------------------------------------------------
# FastAPI Dependencies (replace module-level singletons)
# ---------------------------------------------------------------------------
async def get_or_create_user(db: AsyncSession, platform: str, platform_user_id: str) -> User:
    """Helper to get or create a user across platforms"""
    stmt = select(User).where(User.platform == platform,
                              User.platform_user_id == platform_user_id)
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
    stmt = select(EmotionHistory).where(
        EmotionHistory.conversation_id == conversation_id
    ).order_by(desc(EmotionHistory.timestamp)).limit(10)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    history = [
        EmotionScore(
            category=EmotionCategory(row.category),
            intensity=float(row.intensity),
            timestamp=row.timestamp
        )
        for row in reversed(rows)
    ]
    return EmotionTracker(history=history)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def verify_signature(platform: str, body: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature"""
    verifier = get_verifier(platform, secret)
    if verifier:
        return verifier.verify(body, signature)
    return False


# ---------------------------------------------------------------------------
# Core message processing (refactored to accept state explicitly)
# ---------------------------------------------------------------------------
async def process_webhook_message(
    db: AsyncSession,
    state: AppState,
    platform: str,
    platform_user_id: str,
    text_content: str,
    lang: str = "zh-TW",
) -> tuple[str, str]:
    """Generic message processing logic with Metrics and Tracing.

    Args:
        db: Database session.
        state: AppState with all initialized services.
        platform: Messaging platform name.
        platform_user_id: Platform-specific user ID.
        text_content: Raw message text.
        lang: Language code for i18n.

    Returns:
        Tuple of (response_content, knowledge_source).
    """
    start_time = time.time()

    with tracer.start_as_current_span(f"process_{platform}_message") as span:
        span.set_attribute("platform", platform)
        span.set_attribute("user_id", platform_user_id)

        # 1. Get user and active conversation
        user = await get_or_create_user(db, platform, platform_user_id)
        conv = await get_active_conversation(db, user)

        # 2. Sanitize and Security checks
        clean_text = state.sanitizer.sanitize(text_content)
        security_check = state.prompt_defense.check_input(clean_text)
        if not security_check.is_safe:
            state.logger.warn("prompt_injection_detected", platform=platform,
                              reason=security_check.blocked_reason)
            return "Security violation detected", "blocked"

        # 3. PII masking
        mask_result = state.pii_masking.mask(clean_text)
        processed_text = mask_result.masked_text

        # 4. DST: Process Turn
        intent = "inquiry" if any(k in clean_text for k in [
            "詢問", "查詢", "什麼", "如何"]) else None
        dst_state = state.dst_manager.process_turn(
            int(conv.id), intent, {"content": clean_text})

        # 5. Emotion Tracking
        sentiment = "negative" if any(k in clean_text for k in [
            "生氣", "爛", "慢", "不爽", "差"]) else "neutral"
        category = EmotionCategory.NEGATIVE if sentiment == "negative" else EmotionCategory.NEUTRAL

        MESSAGE_SENTIMENT.labels(platform=platform).observe(
            0.1 if sentiment == "negative" else 0.8)

        db.add(EmotionHistory(
            conversation_id=conv.id,
            category=category.value,
            intensity=0.8
        ))

        tracker = await get_emotion_tracker(db, int(conv.id))
        tracker.add(EmotionScore(category=category, intensity=0.8))

        # 6. Response Logic
        allowed_layers = state.degradation_manager.get_allowed_layers()

        if state.pii_masking.should_escalate(clean_text) or tracker.should_escalate():
            response_content = i18n.translate("escalate", lang)
            knowledge_source = "escalate"
        else:
            use_llm = allowed_layers.get("llm", True)
            knowledge_layer = HybridKnowledgeV7(db, llm_client=use_llm)

            try:
                llm_start = time.time()
                result = await knowledge_layer.query(
                    processed_text,
                    user_context={"state": dst_state.current_state.value}
                )
                llm_duration = time.time() - llm_start
                state.degradation_manager.update_metrics(llm_latency=llm_duration, llm_success=True)

                response_content = result.content
                knowledge_source = result.source

                if knowledge_source == "llm":
                    LLM_TOKEN_USAGE.labels(model="simulated").inc(50)
            except Exception as e:
                state.logger.error("knowledge_query_failed", error=str(e))
                state.degradation_manager.update_metrics(llm_success=False)
                response_content = i18n.translate("error", lang)
                knowledge_source = "error"

        # 7. Save Messages (with Encryption and Cost Model)
        encrypted_user_content = state.encryption_service.encrypt(processed_text)
        duration_ms = int((time.time() - start_time) * 1000)

        # Cost Model: fixed cost per source
        cost_map = {"rule": 0.001, "rag": 0.005, "llm": 0.02, "escalate": 0.05}
        raw_cost = cost_map.get(knowledge_source, 0.0)

        today = datetime.utcnow().date()
        daily_spend_stmt = select(func.sum(Conversation.resolution_cost)).where(
            text("DATE(started_at) = :today")).params(today=today)
        daily_spend_result = await db.execute(daily_spend_stmt)
        current_daily_spend = float(daily_spend_result.scalar() or 0.0)

        cost = state.cost_model.apply_daily_cap(current_daily_spend, raw_cost, cap=DAILY_COST_CAP)

        if cost < raw_cost:
            state.logger.warn("daily_cost_cap_exceeded", raw_cost=raw_cost, allowed_cost=cost)

        db.add(Message(
            conversation_id=conv.id,
            role="user",
            content=encrypted_user_content,
            intent_detected=dst_state.primary_intent,
            duration_ms=duration_ms
        ))
        db.add(Message(
            conversation_id=conv.id,
            role="assistant",
            content=response_content,
            knowledge_source=knowledge_source,
            confidence=0.9 if knowledge_source != "llm" else 0.85
        ))

        conv.dst_state = {
            "current": dst_state.current_state.value, "turn": dst_state.turn_count}
        conv.resolution_cost = float((conv.resolution_cost or 0.0) + cost)
        conv.response_time_ms = int((conv.response_time_ms or 0) + duration_ms)

        # 8. Async Work
        if state.worker:
            await state.worker.produce("omnibot:analytics", {
                "conversation_id": str(conv.id),
                "platform": platform,
                "sentiment": sentiment,
                "knowledge_source": knowledge_source,
                "cost": cost
            })

        REQUEST_LATENCY.labels(endpoint=f"webhook_{platform}").observe(time.time() - start_time)
        return response_content, knowledge_source


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------
@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_telegram_bot_api_secret_token: Optional[str] = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> Any:
    """Telegram bot webhook"""
    state = get_state()
    REQUEST_COUNT.labels(method="POST", endpoint="telegram", platform="telegram").inc()
    body = await request.body()

    client_ip = state.ip_whitelist.get_client_ip(request)
    if not state.ip_whitelist.is_allowed(client_ip):
        state.logger.warn("telegram_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if not await state.rate_limiter.check("telegram", "user"):
        raise HTTPException(status_code=429, detail=i18n.translate("rate_limit"))

    if x_telegram_bot_api_secret_token and TELEGRAM_BOT_TOKEN:
        if not verify_signature("telegram", body, x_telegram_bot_api_secret_token, TELEGRAM_BOT_TOKEN):
            state.logger.warn("telegram_invalid_signature")
            return JSONResponse(status_code=401, content={"success": False, "error": "Invalid signature"})

    data = await request.json()
    message_data = data.get("message", {})
    platform_user_id = str(message_data.get("from", {}).get("id", ""))
    text_content = message_data.get("text", "")

    response_content, _ = await process_webhook_message(
        db, state, "telegram", platform_user_id, text_content)

    await db.commit()
    return {"success": True, "data": {"response": response_content}}


@app.post("/webhook/line")
async def line_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_line_signature: Optional[str] = Header(None, alias="X-Line-Signature"),
) -> Any:
    """LINE messaging webhook"""
    state = get_state()
    REQUEST_COUNT.labels(method="POST", endpoint="line", platform="line").inc()
    body = await request.body()

    client_ip = state.ip_whitelist.get_client_ip(request)
    if not state.ip_whitelist.is_allowed(client_ip):
        state.logger.warn("line_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if x_line_signature and LINE_CHANNEL_SECRET:
        if not verify_signature("line", body, x_line_signature, LINE_CHANNEL_SECRET):
            state.logger.warn("line_invalid_signature")
            return JSONResponse(status_code=401, content={"success": False, "error": "Invalid signature"})

    body_json = await request.json()
    for event in body_json.get("events", []):
        if event.get("type") == "message":
            platform_user_id = str(event["source"]["userId"])
            text_content = event["message"].get("text", "")
            await process_webhook_message(db, state, "line", platform_user_id, text_content)

    await db.commit()
    return {"success": True, "data": {}}


@app.post("/webhook/messenger")
async def messenger_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
) -> Any:
    """Facebook Messenger webhook"""
    state = get_state()
    REQUEST_COUNT.labels(method="POST", endpoint="messenger", platform="messenger").inc()
    body = await request.body()

    client_ip = state.ip_whitelist.get_client_ip(request)
    if not state.ip_whitelist.is_allowed(client_ip):
        state.logger.warn("messenger_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    if x_hub_signature and MESSENGER_APP_SECRET:
        if not verify_signature("messenger", body, x_hub_signature, MESSENGER_APP_SECRET):
            state.logger.warn("messenger_invalid_signature")
            return JSONResponse(status_code=401, content={"success": False, "error": "Invalid signature"})

    data = await request.json()
    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = str(messaging["sender"]["id"])
            text_content = messaging["message"].get("text", "")
            await process_webhook_message(db, state, "messenger", sender_id, text_content)

    await db.commit()
    return {"success": True, "data": {}}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """WhatsApp Business webhook"""
    state = get_state()
    REQUEST_COUNT.labels(method="POST", endpoint="whatsapp", platform="whatsapp").inc()

    client_ip = state.ip_whitelist.get_client_ip(request)
    if not state.ip_whitelist.is_allowed(client_ip):
        state.logger.warn("whatsapp_ip_not_whitelisted", client_ip=client_ip)
        return JSONResponse(status_code=403, content={})

    data = await request.json()
    results = []
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                sender_id = message["from"]
                text_content = message.get("text", {}).get("body", "")
                response, _ = await process_webhook_message(
                    db, state, "whatsapp", sender_id, text_content)
                results.append(response)

    await db.commit()
    return {"success": True, "data": {"responses": results}}


# ---------------------------------------------------------------------------
# KPI Dashboard
# ---------------------------------------------------------------------------
@app.get("/api/v1/kpi/dashboard")
async def get_kpi_dashboard(
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("system", "read")),
) -> Any:
    """Enterprise KPI Dashboard - Phase 3 Real Implementation"""
    kpi = KPIManager(db)
    total_convs = await kpi.get_total_conversations()
    avg_res_time = await kpi.get_avg_resolution_time()
    esc_rate = await kpi.get_escalation_rate()
    hit_rate = await kpi.get_knowledge_hit_rate()
    sla_rate = await kpi.get_sla_compliance_rate()
    revenue = await kpi.get_revenue_per_conversation()
    daily = await kpi.get_daily_breakdown(days=7)

    return {
        "success": True,
        "data": {
            "summary": {
                "total_conversations": total_convs,
                "avg_resolution_time_sec": round(avg_res_time, 2),
                "escalation_rate": round(esc_rate * 100, 2),
                "knowledge_hit_rate": round(hit_rate * 100, 2),
                "sla_compliance_rate": round(sla_rate * 100, 2),
                "estimated_revenue_per_conv": round(revenue, 2),
            },
            "daily_trends": daily,
        },
    }


# ---------------------------------------------------------------------------
# Knowledge Base Query
# ---------------------------------------------------------------------------
@app.get("/api/v1/knowledge")
async def query_knowledge(
    q: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("knowledge", "read")),
) -> Any:
    """Query knowledge base with real database filtering"""
    offset = (page - 1) * limit
    stmt = select(KnowledgeBase).where(KnowledgeBase.is_active == True)

    if q:
        stmt = stmt.where(or_(
            KnowledgeBase.question.ilike(f"%{q}%"),
            KnowledgeBase.answer.ilike(f"%{q}%"),
        ))
    if category:
        stmt = stmt.where(KnowledgeBase.category == category)

    stmt = stmt.order_by(KnowledgeBase.id.desc()).offset(offset).limit(limit + 1)
    result = await db.execute(stmt)
    items = result.scalars().all()

    has_next = len(items) > limit
    if has_next:
        items = items[:limit]

    return {
        "success": True,
        "data": {
            "items": [
                {
                    "id": item.id,
                    "question": item.question,
                    "answer": item.answer,
                    "category": item.category,
                    "version": item.version,
                }
                for item in items
            ],
            "has_next": has_next,
            "page": page,
            "limit": limit,
        },
    }


# ---------------------------------------------------------------------------
# Escalation endpoint
# ---------------------------------------------------------------------------
@app.post("/api/v1/escalate")
async def escalate_conversation(
    escalation: EscalationRequest,
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("escalation", "write")),
) -> Any:
    """Manually escalate a conversation to a human agent"""
    from app.services.escalation import EscalationManager
    state = get_state()
    esc_manager = EscalationManager(db)
    conv = await esc_manager.escalate(
        conversation_id=escalation.conversation_id,
        reason=escalation.reason or "manual_escalation",
        priority=escalation.priority,
    )
    await db.commit()
    return {"success": True, "data": {"conversation_id": conv.id, "status": conv.status}}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check() -> Any:
    """Health check endpoint"""
    state = get_state()
    return {
        "status": "ok",
        "version": "1.1.1",
        "worker_alive": state.worker is not None,
    }
