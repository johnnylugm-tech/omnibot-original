"""Escalation manager with SLA tracking - Phase 2"""
from datetime import datetime, timedelta
from typing import List, Union
from sqlalchemy import select, update, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EscalationRequest
from app.models.database import EscalationQueue


class EscalationManager:
    """Phase 2: Escalation with SLA tracking and DB persistence"""

    # Priority 0: P0 (15m), 1: P1 (30m), 2: P2 (120m)
    SLA_MINUTES = {
        0: 15,
        1: 30,
        2: 120
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, request: EscalationRequest, priority: Union[int, str] = 0) -> int:
        """Create escalation ticket with SLA deadline"""
        # Support both int and string for backward compatibility/flexibility
        if isinstance(priority, str):
            p_map = {"urgent": 0, "high": 1, "normal": 2}
            p_val = p_map.get(priority.lower(), 2)
        else:
            p_val = priority

        minutes = self.SLA_MINUTES.get(p_val, 30)
        deadline = datetime.utcnow() + timedelta(minutes=minutes)

        ticket = EscalationQueue(
            conversation_id=request.conversation_id,
            reason=request.reason,
            priority=p_val,
            sla_deadline=deadline
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
                EscalationQueue.sla_deadline < now,
                EscalationQueue.resolved_at == None
            )
            .order_by(
                desc(EscalationQueue.priority),
                asc(EscalationQueue.queued_at)
            )
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
