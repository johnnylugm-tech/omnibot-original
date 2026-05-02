"""High-level KPI management and business intelligence service."""
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Conversation, EscalationQueue, Message


class KPIManager:
    """Aggregates metrics and database logs to provide business KPIs."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_total_conversations(self) -> int:
        """Returns total number of conversations in the system."""
        stmt = select(func.count(Conversation.id))
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_avg_resolution_time(self) -> float:
        """Calculates average time from start to resolution in seconds."""
        stmt = select(func.avg(Conversation.response_time_ms))
        result = await self.db.execute(stmt)
        avg_ms = result.scalar() or 0.0
        return avg_ms / 1000.0

    async def get_escalation_rate(self) -> float:
        """Returns percentage of conversations that were escalated."""
        total_stmt = select(func.count(Conversation.id))
        esc_stmt = select(func.count(EscalationQueue.id))

        total = await self.db.execute(total_stmt)
        esc = await self.db.execute(esc_stmt)

        total_val = total.scalar() or 0
        if total_val == 0:
            return 0.0
        return (esc.scalar() or 0) / total_val

    async def get_knowledge_hit_rate(self) -> float:
        """Returns percentage of queries satisfied by knowledge base (rule or rag)."""
        total_stmt = select(func.count(Message.id)).where(Message.role == "assistant")
        hit_stmt = select(func.count(Message.id)).where(
            Message.role == "assistant",
            Message.knowledge_source.in_(["rule", "rag"])
        )

        total = await self.db.execute(total_stmt)
        hit = await self.db.execute(hit_stmt)

        total_val = total.scalar() or 0
        if total_val == 0:
            return 0.0
        return (hit.scalar() or 0) / total_val

    async def get_sla_compliance_rate(self) -> float:
        """Returns percentage of escalations handled within SLA."""
        total_stmt = select(func.count(EscalationQueue.id)).where(EscalationQueue.resolved_at.isnot(None))
        compliant_stmt = select(func.count(EscalationQueue.id)).where(
            EscalationQueue.resolved_at.isnot(None),
            EscalationQueue.resolved_at <= EscalationQueue.sla_deadline
        )

        total = await self.db.execute(total_stmt)
        compliant = await self.db.execute(compliant_stmt)

        total_val = total.scalar() or 0
        if total_val == 0:
            return 1.0  # Default to compliant if no escalations
        return (compliant.scalar() or 0) / total_val

    async def get_revenue_per_conversation(self) -> float:
        """Calculates cost-adjusted value. Simplified: (Fixed Value - resolution_cost)."""
        FIXED_VALUE = 1.0  # $1 per conversation
        stmt = select(func.avg(Conversation.resolution_cost))
        result = await self.db.execute(stmt)
        avg_cost = result.scalar() or 0.0
        return max(0.0, FIXED_VALUE - avg_cost)

    async def get_daily_breakdown(self, days: int = 30) -> List[Dict[str, Any]]:
        """Returns a daily history of key metrics using a group by date."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        # Using text for easier date grouping in Postgres
        stmt = text("""
            SELECT 
                DATE(started_at) as date,
                COUNT(id) as total,
                AVG(response_time_ms) as avg_time,
                AVG(resolution_cost) as avg_cost
            FROM conversations
            WHERE started_at >= :cutoff
            GROUP BY DATE(started_at)
            ORDER BY date DESC
        """)
        result = await self.db.execute(stmt, {"cutoff": cutoff})
        return [
            {"date": str(row[0]), "total": row[1], "avg_time_ms": row[2], "avg_cost": row[3]}
            for row in result.fetchall()
        ]
