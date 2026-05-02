"""Conversations listing route.

Phase 3 refactor: extracted from app/api/__init__.py
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Conversation, get_db
from app.security.rbac import rbac

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("conversations", "read")),
) -> Any:
    """List conversations from real DB with pagination"""
    offset = (page - 1) * limit
    stmt = (
        select(Conversation)
        .order_by(Conversation.started_at.desc())
        .offset(offset)
        .limit(limit + 1)
    )
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
                    "id": c.id,
                    "platform": c.platform,
                    "status": c.status,
                    "started_at": (c.started_at.isoformat() if c.started_at else None),
                }
                for c in items
            ],
            "page": page,
            "limit": limit,
            "has_next": has_next,
        },
    }
