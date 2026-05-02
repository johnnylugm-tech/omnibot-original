"""API Helper utilities for webhook processing and user management."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import User, Conversation
from app.services.emotion import EmotionTracker
from typing import Optional

async def get_or_create_user(db: AsyncSession, platform: str, platform_user_id: str) -> User:
    stmt = select(User).where(User.platform == platform, User.platform_user_id == platform_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(platform=platform, platform_user_id=platform_user_id)
        db.add(user)
        await db.flush()
    return user

async def get_active_conversation(db: AsyncSession, user_id: int) -> Conversation:
    stmt = select(Conversation).where(Conversation.user_id == user_id, Conversation.status != "resolved")
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        conv = Conversation(user_id=user_id)
        db.add(conv)
        await db.flush()
    return conv

def get_emotion_tracker(history: list) -> EmotionTracker:
    # Convert DB history to EmotionScore objects and return tracker
    from app.services.emotion import EmotionScore, EmotionCategory
    scores = []
    for h in history:
        scores.append(EmotionScore(category=EmotionCategory(h.category), intensity=h.intensity, timestamp=h.timestamp))
    return EmotionTracker(history=scores)
