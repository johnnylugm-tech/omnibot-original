"""Knowledge base CRUD endpoints and conversation listing."""

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import rbac
from app.models.database import Conversation, KnowledgeBase, get_db

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


@router.get("/knowledge")
async def query_knowledge(
    q: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("knowledge", "read")),
) -> dict[str, Any]:
    """Query knowledge base with real database filtering."""
    offset = (page - 1) * limit
    stmt = select(KnowledgeBase).where(KnowledgeBase.is_active)

    if q:
        stmt = stmt.where(
            or_(
                KnowledgeBase.question.ilike(f"%{q}%"),
                KnowledgeBase.answer.ilike(f"%{q}%"),
            )
        )
    if category:
        stmt = stmt.where(KnowledgeBase.category == category)

    stmt = (
        select(KnowledgeBase)
        .order_by(KnowledgeBase.id.desc())
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
                    "id": k.id,
                    "question": k.question,
                    "category": k.category,
                    "answer": k.answer,
                }
                for k in items
            ],
            "page": page,
            "limit": limit,
            "has_next": has_next,
        },
    }


@router.post("/knowledge")
async def create_knowledge(
    item: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("knowledge", "write")),
) -> dict[str, Any]:
    """Create knowledge entry in DB."""
    new_k = KnowledgeBase(
        category=item.get("category", "General"),
        question=item.get("question", ""),
        answer=item.get("answer", ""),
        keywords=item.get("keywords", []),
        is_active=True,
        version=1,
    )
    db.add(new_k)
    await db.commit()
    await db.refresh(new_k)
    return {"success": True, "data": {"id": new_k.id}}


@router.get("/conversations")
async def list_conversations(
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("conversations", "read")),
) -> dict[str, Any]:
    """List conversations from real DB with pagination."""
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


@router.put("/knowledge/{id}")
async def update_knowledge(
    id: int,
    item: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("knowledge", "write")),
) -> dict[str, Any]:
    """Update knowledge entry in DB."""
    stmt = select(KnowledgeBase).where(KnowledgeBase.id == id)
    result = await db.execute(stmt)
    k = result.scalar_one_or_none()

    if not k:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    for key, value in item.items():
        if hasattr(k, key):
            setattr(k, key, value)

    k.version = int(k.version) + 1  # type: ignore[assignment]
    await db.commit()
    return {"success": True, "data": {"id": id}}


@router.delete("/knowledge/{id}")
async def delete_knowledge(
    id: int,
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("knowledge", "delete")),
) -> dict[str, Any]:
    """Soft delete knowledge entry."""
    stmt = select(KnowledgeBase).where(KnowledgeBase.id == id)
    result = await db.execute(stmt)
    k = result.scalar_one_or_none()

    if not k:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    k.is_active = False  # type: ignore[assignment]
    await db.commit()
    return {"success": True, "data": {"deleted": True}}


@router.post("/knowledge/bulk")
async def bulk_import(
    items: list[dict] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user_role: str = Depends(rbac.require("knowledge", "write")),
) -> dict[str, Any]:
    """Bulk import knowledge entries."""
    for item in items:
        new_k = KnowledgeBase(
            category=item.get("category", "General"),
            question=item.get("question", ""),
            answer=item.get("answer", ""),
            keywords=item.get("keywords", []),
            is_active=True,
            version=1,
        )
        db.add(new_k)
    await db.commit()
    return {"success": True, "data": {"imported": len(items)}}
