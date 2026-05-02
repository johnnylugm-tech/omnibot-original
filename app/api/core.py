"""Core shared processing logic for webhook handlers.

Phase 3 refactor: extracted from app/api/__init__.py
process_webhook_message is used by all 4 platform webhook handlers.
"""
import time
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Conversation, EmotionHistory, Message
from app.security import InputSanitizer, PIIMasking, PromptInjectionDefense
from app.security.encryption import EncryptionService
from app.services.degradation import DegradationManager
from app.services.emotion import EmotionCategory, EmotionScore
from app.services.dst import DSTManager
from app.services.knowledge import HybridKnowledgeV7
from app.utils.cost_model import CostModel
from app.utils.i18n import i18n
from app.utils.logger import StructuredLogger
from app.utils.metrics import LLM_TOKEN_USAGE, MESSAGE_SENTIMENT, REQUEST_LATENCY
from app.utils.tracing import tracer
from app.api.helpers import get_active_conversation, get_emotion_tracker, get_or_create_user
from app.api.shared_state import state

logger = StructuredLogger("omnibot")
encryption_service = EncryptionService()
degradation_manager = DegradationManager()
DSTManager_instance = DSTManager()
cost_model = CostModel()
DAILY_COST_CAP = 10.0

INTENT_KEYWORDS = ["詢問", "查詢", "什麼", "如何"]
NEGATIVE_KEYWORDS = ["生氣", "爛", "慢", "不爽", "差"]


async def process_webhook_message(
    db: AsyncSession,
    platform: str,
    platform_user_id: str,
    text_content: str,
    lang: str = "zh-TW",
) -> tuple[str, str]:
    """Generic message processing logic shared by all webhook handlers.

    Returns (response_content, knowledge_source).
    """
    start_time = time.time()

    with tracer.start_as_current_span(f"process_{platform}_message") as span:
        span.set_attribute("platform", platform)
        span.set_attribute("user_id", platform_user_id)

        user = await get_or_create_user(db, platform, platform_user_id)
        conv = await get_active_conversation(db, user)

        clean_text = InputSanitizer().sanitize(text_content)
        security_check = PromptInjectionDefense().check_input(clean_text)
        if not security_check.is_safe:
            logger.warn(
                "prompt_injection_detected",
                platform=platform,
                reason=security_check.blocked_reason,
            )
            return "Security violation detected", "blocked"

        mask_result = PIIMasking().mask(clean_text)
        processed_text = mask_result.masked_text

        intent = "inquiry" if any(k in clean_text for k in INTENT_KEYWORDS) else None
        dst_state = DSTManager_instance.process_turn(
            int(conv.id), intent, {"content": clean_text}
        )

        sentiment = "negative" if any(k in clean_text for k in NEGATIVE_KEYWORDS) else "neutral"
        category = EmotionCategory.NEGATIVE if sentiment == "negative" else EmotionCategory.NEUTRAL

        MESSAGE_SENTIMENT.labels(platform=platform).observe(
            0.1 if sentiment == "negative" else 0.8
        )

        db.add(
            EmotionHistory(
                conversation_id=conv.id, category=category.value, intensity=0.8
            )
        )

        tracker = await get_emotion_tracker(db, int(conv.id))
        tracker.add(EmotionScore(category=category, intensity=0.8))

        allowed_layers = degradation_manager.get_allowed_layers()

        if PIIMasking().should_escalate(clean_text) or tracker.should_escalate():
            response_content = i18n.translate("escalate", lang)
            knowledge_source = "escalate"
        else:
            use_llm = allowed_layers.get("llm", True)
            knowledge_layer = HybridKnowledgeV7(db, llm_client=use_llm)

            try:
                llm_start = time.time()
                result = await knowledge_layer.query(
                    processed_text, user_context={"state": dst_state.current_state.value}
                )
                llm_duration = time.time() - llm_start
                degradation_manager.update_metrics(llm_latency=llm_duration, llm_success=True)
                response_content = result.content
                knowledge_source = result.source
                if knowledge_source == "llm":
                    LLM_TOKEN_USAGE.labels(model="simulated").inc(50)
            except Exception as e:
                logger.error("knowledge_query_failed", error=str(e))
                degradation_manager.update_metrics(llm_success=False)
                response_content = i18n.translate("error", lang)
                knowledge_source = "error"

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
        daily_spend_result = await db.execute(daily_spend_stmt)
        current_daily_spend = float(daily_spend_result.scalar() or 0.0)
        cost = cost_model.apply_daily_cap(current_daily_spend, raw_cost, cap=DAILY_COST_CAP)

        if cost < raw_cost:
            logger.warn("daily_cost_cap_exceeded", raw_cost=raw_cost, allowed_cost=cost)

        db.add(
            Message(
                conversation_id=conv.id,
                role="user",
                content=encrypted_user_content,
                intent_detected=dst_state.primary_intent,
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

        conv.dst_state = {"current": dst_state.current_state.value, "turn": dst_state.turn_count}  # type: ignore[assignment]
        conv.resolution_cost = float((conv.resolution_cost or 0.0) + cost)  # type: ignore[assignment]
        conv.response_time_ms = int((conv.response_time_ms or 0) + duration_ms)  # type: ignore[assignment]

        if state.worker:
            await state.worker.produce(
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
