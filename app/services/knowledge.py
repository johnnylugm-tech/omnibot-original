"""Knowledge Layer Phase 1 - Rule matching only"""
from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import KnowledgeBase
from app.models import KnowledgeResult


class KnowledgeLayerV1:
    """Phase 1: Rule matching + escalation fallback"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def query(self, query_text: str) -> KnowledgeResult:
        result = await self._rule_match(query_text)
        if result is not None and result.confidence > 0.7:
            return result
        return self._escalate(query_text, reason="no_rule_match")

    async def _rule_match(self, query_text: str) -> Optional[KnowledgeResult]:
        results = await self._rule_match_list(query_text)
        return results[0] if results else None

    async def _rule_match_list(self, query_text: str) -> List[KnowledgeResult]:
        """SQL-based rule matching for Phase 1"""
        stmt = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.is_active == True,
                or_(
                    KnowledgeBase.question.ilike(f"%{query_text}%"),
                    KnowledgeBase.keywords.any(query_text)
                )
            )
            .order_by(KnowledgeBase.version.desc())
            .limit(5)
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        
        return [
            KnowledgeResult(
                id=row.id,
                content=row.answer,
                confidence=0.95 if query_text.lower() in row.question.lower() else 0.7,
                source="rule",
                knowledge_id=row.id,
            )
            for row in rows
        ]

    def _escalate(self, query_text: str, reason: str) -> KnowledgeResult:
        return KnowledgeResult(
            id=-1,
            content="正在為您轉接人工客服，請稍候...",
            confidence=0.0,
            source="escalate",
        )
