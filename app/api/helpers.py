"""API Helper utilities for webhook processing and user management."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Conversation, User
from app.services.emotion import EmotionTracker


async def get_or_create_user(
    db: AsyncSession, platform: str, platform_user_id: str
) -> User:
    stmt = select(User).where(
        User.platform == platform, User.platform_user_id == platform_user_id
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(platform=platform, platform_user_id=platform_user_id)
        db.add(user)
        await db.flush()
    return user


async def get_active_conversation(
    db: AsyncSession, unified_user_id: Any, platform: str
) -> Conversation:
    stmt = select(Conversation).where(
        Conversation.unified_user_id == unified_user_id,
        Conversation.status != "resolved",
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        conv = Conversation(unified_user_id=unified_user_id, platform=platform)
        db.add(conv)
        await db.flush()
    return conv


def get_emotion_tracker(history: list) -> EmotionTracker:
    # Convert DB history to EmotionScore objects and return tracker
    from app.services.emotion import EmotionCategory, EmotionScore

    scores = []
    for h in history:
        scores.append(
            EmotionScore(
                category=EmotionCategory(h.category),
                intensity=h.intensity,
                timestamp=h.timestamp,
            )
        )
    return EmotionTracker(history=scores)
