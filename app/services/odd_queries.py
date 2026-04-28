"""
ODD (Operational Data Driven) Query Manager - Phase 3
Contains 13 core analysis SQL queries for KPI and system monitoring.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

class ODDQueryManager:
    """
    Manager for ODD SQL queries.
    Provides methods to execute 13 core analysis queries.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_query(self, query: str, params: dict = None) -> List[Dict[str, Any]]:
        result = await self.db.execute(text(query), params or {})
        return [dict(row._mapping) for row in result.fetchall()]

    # --- Phase 1 Queries ---

    async def get_fcr_rate(self) -> float:
        """1. FCR Rate rounded to 2 decimals"""
        sql = """
        SELECT ROUND(
            CAST(COUNT(CASE WHEN first_contact_resolution = TRUE THEN 1 END) AS NUMERIC) / 
            NULLIF(COUNT(*), 0), 2
        ) as fcr_rate
        FROM conversations;
        """
        res = await self.execute_query(sql)
        return float(res[0]['fcr_rate']) if res and res[0]['fcr_rate'] is not None else 0.0

    async def get_latency_p95_by_platform(self) -> List[Dict[str, Any]]:
        """2. p95 Latency grouped by platform"""
        sql = """
        SELECT platform, 
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_latency
        FROM conversations
        GROUP BY platform;
        """
        return await self.execute_query(sql)

    async def get_knowledge_hit_by_source(self) -> List[Dict[str, Any]]:
        """3. Knowledge hit count aggregated by source"""
        sql = """
        SELECT knowledge_source, COUNT(*) as hit_count
        FROM messages
        WHERE role = 'assistant' AND knowledge_source IS NOT NULL
        GROUP BY knowledge_source;
        """
        return await self.execute_query(sql)

    # --- Phase 2 Queries ---

    async def get_csat_stats(self) -> Dict[str, Any]:
        """4. CSAT Avg and p95"""
        sql = """
        SELECT AVG(satisfaction_score) as avg_csat,
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY satisfaction_score) as p95_csat
        FROM conversations
        WHERE satisfaction_score IS NOT NULL;
        """
        res = await self.execute_query(sql)
        return res[0] if res else {"avg_csat": 0.0, "p95_csat": 0.0}

    async def get_knowledge_hit_distribution(self) -> List[Dict[str, Any]]:
        """5. Knowledge hit distribution with percentage"""
        sql = """
        WITH total AS (SELECT COUNT(*) as cnt FROM messages WHERE role = 'assistant')
        SELECT knowledge_source, 
               COUNT(*) as count,
               ROUND(CAST(COUNT(*) AS NUMERIC) / (SELECT cnt FROM total) * 100, 2) as percentage
        FROM messages
        WHERE role = 'assistant'
        GROUP BY knowledge_source;
        """
        return await self.execute_query(sql)

    async def get_feedback_analysis(self) -> List[Dict[str, Any]]:
        """6. Feedback analysis joined with messages"""
        sql = """
        SELECT f.feedback, f.comment, m.content as message_content, c.platform
        FROM feedback f
        JOIN messages m ON f.message_id = m.id
        JOIN conversations c ON m.conversation_id = c.id;
        """
        return await self.execute_query(sql)

    async def get_sla_compliance_by_priority(self) -> List[Dict[str, Any]]:
        """7. SLA compliance rate by priority"""
        sql = """
        SELECT priority,
               ROUND(
                   CAST(COUNT(CASE WHEN resolved_at <= sla_deadline THEN 1 END) AS NUMERIC) / 
                   NULLIF(COUNT(*), 0) * 100, 2
               ) as compliance_rate
        FROM escalation_queue
        GROUP BY priority;
        """
        return await self.execute_query(sql)

    async def get_emotion_stats(self) -> List[Dict[str, Any]]:
        """8. Emotion stats grouped by date and category"""
        sql = """
        SELECT DATE(created_at) as date, category, COUNT(*) as count
        FROM emotion_history
        GROUP BY DATE(created_at), category
        ORDER BY date DESC, count DESC;
        """
        return await self.execute_query(sql)

    async def get_security_block_rate(self) -> float:
        """9. Security block rate percentage"""
        sql = """
        SELECT ROUND(
            CAST(COUNT(CASE WHEN risk_level IN ('high', 'critical') THEN 1 END) AS NUMERIC) / 
            NULLIF(COUNT(*), 0) * 100, 2
        ) as block_rate
        FROM audit_logs
        WHERE action = 'security_block';
        """
        res = await self.execute_query(sql)
        return float(res[0]['block_rate']) if res and res[0]['block_rate'] is not None else 0.0

    # --- Phase 3 Queries ---

    async def get_knowledge_source_cost(self) -> List[Dict[str, Any]]:
        """10. Cost analysis by knowledge source"""
        sql = """
        SELECT knowledge_source, SUM(resolution_cost) as total_cost
        FROM conversations c
        JOIN messages m ON c.id = m.conversation_id
        WHERE m.role = 'assistant'
        GROUP BY knowledge_source;
        """
        return await self.execute_query(sql)

    async def get_pii_masking_rate(self) -> float:
        """11. PII Masking rate (PII messages / Total messages)"""
        sql = """
        SELECT ROUND(
            CAST(COUNT(CASE WHEN pii_types IS NOT NULL THEN 1 END) AS NUMERIC) / 
            NULLIF(COUNT(*), 0) * 100, 2
        ) as masking_rate
        FROM messages;
        """
        res = await self.execute_query(sql)
        return float(res[0]['masking_rate']) if res and res[0]['masking_rate'] is not None else 0.0

    async def get_rbac_denial_audit(self) -> List[Dict[str, Any]]:
        """12. RBAC denial audit by role and resource"""
        sql = """
        SELECT role, resource, COUNT(*) as denial_count
        FROM audit_logs
        WHERE action = 'rbac_denied'
        GROUP BY role, resource;
        """
        return await self.execute_query(sql)

    async def get_ab_test_performance(self) -> List[Dict[str, Any]]:
        """13. A/B test variant performance (conversion rate)"""
        sql = """
        SELECT experiment_id, variant, 
               AVG(metric_value) as avg_metric,
               SUM(sample_size) as total_samples
        FROM experiment_results
        GROUP BY experiment_id, variant;
        """
        return await self.execute_query(sql)
