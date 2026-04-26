"""Escalation manager with SLA tracking - Phase 2"""
from datetime import datetime, timedelta
from app.models import EscalationRequest
from app.models.database import EscalationQueue
from sqlalchemy.ext.asyncio import AsyncSession


class EscalationManager:
    """Phase 2: Escalation with SLA tracking and DB persistence"""

    SLA_MINUTES = {
        "urgent": 5,
        "high": 15,
        "normal": 30
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, request: EscalationRequest, priority: str = "normal") -> int:
        """Create escalation ticket with SLA deadline"""
        minutes = self.SLA_MINUTES.get(priority.lower(), 30)
        deadline = datetime.utcnow() + timedelta(minutes=minutes)
        
        ticket = EscalationQueue(
            conversation_id=request.conversation_id,
            reason=request.reason,
            priority=1 if priority == "urgent" else 2 if priority == "high" else 3,
            sla_deadline=deadline
        )
        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket.id

    async def assign(self, escalation_id: int, agent_id: str) -> None:
        """Assign ticket to an agent"""
        from sqlalchemy import update
        stmt = (
            update(EscalationQueue)
            .where(EscalationQueue.id == escalation_id)
            .values(assigned_agent=agent_id, picked_at=datetime.utcnow())
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def resolve(self, escalation_id: int) -> None:
        """Mark ticket as resolved"""
        from sqlalchemy import update
        stmt = (
            update(EscalationQueue)
            .where(EscalationQueue.id == escalation_id)
            .values(resolved_at=datetime.utcnow())
        )
        await self.db.execute(stmt)
        await self.db.commit()
