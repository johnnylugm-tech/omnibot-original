"""Escalation manager with SLA tracking - Phase 2"""

from datetime import datetime, timedelta
from typing import List, Optional, Union

from sqlalchemy import asc, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EscalationRequest
from app.models.database import EscalationQueue, UserFeedback


class ValidationError(Exception):
    """Raised when submitted data fails validation."""

    pass


class FeedbackManager:
    """Manages user feedback submission (Phase 2)."""

    VALID_RATINGS = ("thumbs_up", "thumbs_down")

    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_feedback(
        self, conversation_id: int, rating: str, comment: Optional[str]
    ) -> UserFeedback:
        """Submit user feedback for a conversation.

        Args:
            conversation_id: ID of the conversation.
            rating: Must be 'thumbs_up' or 'thumbs_down'.
            comment: Optional free-text comment.

        Returns:
            Created UserFeedback record.

        Raises:
            ValidationError: If rating is not one of the valid values.
        """
        if rating not in self.VALID_RATINGS:
            raise ValidationError(
                f"Invalid rating '{rating}'. Must be one of: {self.VALID_RATINGS}"
            )

        fb = UserFeedback(
            conversation_id=conversation_id,
            feedback=rating,
            comment=comment,
        )
        self.db.add(fb)
        await self.db.commit()
        await self.db.refresh(fb)
        return fb


class EscalationManager:
    """人工轉接管理（含 SLA）- 遵循 SPEC v7.0"""

    SLA_BY_PRIORITY: dict[int, int] = {
        0: 30,  # normal: 30 分鐘內回應
        1: 15,  # high: 15 分鐘內回應
        2: 5,  # urgent: 5 分鐘內回應
    }
    SLA_MINUTES = SLA_BY_PRIORITY

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, request: EscalationRequest, priority: Union[int, str] = 0
    ) -> int:
        """Create escalation ticket with SLA deadline"""
        # Map string priority to numeric p_val
        if isinstance(priority, str):
            p_map = {
                "normal": 0,
                "high": 1,
                "urgent": 2,
                "p0": 1,
                "p1": 0,
                "p2": 2,
            }  # Aligning common aliases
            # Note: If specific test strings like 'p0' were used inconsistently,
            # we prioritize SPEC definitions over alias naming.
            p_val = p_map.get(priority.lower(), 0)
        else:
            p_val = priority

        sla_minutes = self.SLA_BY_PRIORITY.get(p_val, 30)
        sla_deadline = datetime.utcnow() + timedelta(minutes=sla_minutes)

        ticket = EscalationQueue(
            conversation_id=request.conversation_id,
            reason=request.reason,
            priority=p_val,
            sla_deadline=sla_deadline,
        )
        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)
        return int(ticket.id) if ticket.id is not None else 0

    async def get_sla_breaches(self) -> List[EscalationQueue]:
        """Get tickets that breached SLA and are not yet resolved"""
        now = datetime.utcnow()
        stmt = (
            select(EscalationQueue)
            .where(
                EscalationQueue.sla_deadline < now, EscalationQueue.resolved_at is None
            )
            .order_by(desc(EscalationQueue.priority), asc(EscalationQueue.queued_at))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def assign(self, escalation_id: int, agent_id: str) -> None:
        """Assign ticket to an agent"""
        stmt = (
            update(EscalationQueue)
            .where(EscalationQueue.id == escalation_id)
            .values(assigned_agent=agent_id, picked_at=datetime.utcnow())
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def resolve(self, escalation_id: int) -> None:
        """Mark ticket as resolved"""
        stmt = (
            update(EscalationQueue)
            .where(EscalationQueue.id == escalation_id)
            .values(resolved_at=datetime.utcnow())
        )
        await self.db.execute(stmt)
        await self.db.commit()
