import pytest
import pytest_asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.database import (
    Base, User, Conversation, Message, KnowledgeBase, 
    EscalationQueue, Experiment, Role, RoleAssignment, 
    PIIAuditLog, EmotionHistory, SecurityLog, ExperimentResult
)
import uuid
from datetime import datetime, timedelta

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://omnibot:password@localhost:5433/omnibot")

@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()

async def seed_data(session):
    # 1. Create Users
    admin_uuid = uuid.uuid4()
    user_uuid = uuid.uuid4()
    session.add_all([
        User(unified_user_id=admin_uuid, platform="system", platform_user_id="admin"),
        User(unified_user_id=user_uuid, platform="telegram", platform_user_id="123")
    ])
    await session.flush()
    
    # 2. Conversations & Messages
    # Conv 1: Resolved by Rule (FCR pass)
    conv1 = Conversation(
        unified_user_id=user_uuid, platform="telegram", 
        first_contact_resolution=True, resolution_cost=0.1,
        satisfaction_score=5.0, started_at=datetime.utcnow() - timedelta(days=1)
    )
    session.add(conv1)
    await session.flush()
    session.add_all([
        Message(conversation_id=conv1.id, role="user", content="hello"),
        Message(conversation_id=conv1.id, role="assistant", content="world", 
                knowledge_source="rule", confidence=0.95, created_at=datetime.utcnow(), duration_ms=500)
    ])
    
    # Conv 2: Resolved by RAG (Phase 2)
    conv2 = Conversation(
        unified_user_id=user_uuid, platform="line", 
        first_contact_resolution=True, resolution_cost=0.5,
        satisfaction_score=4.0, started_at=datetime.utcnow()
    )
    session.add(conv2)
    await session.flush()
    session.add_all([
        Message(conversation_id=conv2.id, role="user", content="help"),
        Message(conversation_id=conv2.id, role="assistant", content="rag answer", 
                knowledge_source="rag", confidence=0.85, duration_ms=1500)
    ])
    
    # Conv 3: Escalated (FCR fail)
    conv3 = Conversation(
        unified_user_id=user_uuid, platform="telegram", 
        first_contact_resolution=False, resolution_cost=2.0,
        started_at=datetime.utcnow()
    )
    session.add(conv3)
    await session.flush()
    session.add_all([
        Message(conversation_id=conv3.id, role="user", content="human!"),
        Message(conversation_id=conv3.id, role="assistant", content="escalating", 
                knowledge_source="escalate", confidence=0.0, duration_ms=200)
    ])
    
    # 3. Escalation Queue
    # Ticket 1: Priority 3, met SLA
    session.add(EscalationQueue(
        conversation_id=conv3.id, reason="manual_request", priority=3, 
        sla_deadline=datetime.utcnow() + timedelta(minutes=5),
        resolved_at=datetime.utcnow()
    ))
    
    # 4. Emotion History
    session.add_all([
        EmotionHistory(conversation_id=conv3.id, category="NEGATIVE", intensity=0.9),
        EmotionHistory(conversation_id=conv1.id, category="POSITIVE", intensity=0.8)
    ])
    
    # 5. Security Logs
    session.add_all([
        SecurityLog(conversation_id=conv1.id, layer="L3", blocked=True, block_reason="injection"),
        SecurityLog(conversation_id=conv2.id, layer="L3", blocked=False)
    ])
    
    # 6. Experiments
    exp = Experiment(name="prompt_v2", status="running", variants={}, traffic_split={"control": 50, "test": 50})
    session.add(exp)
    await session.flush()
    session.add(ExperimentResult(experiment_id=exp.id, variant="test", metric_name="fcr", metric_value=0.85, sample_size=100))
    
    # 7. Roles & PII logs
    role = Role(name="admin", permissions={"knowledge": ["read", "write"]})
    session.add(role)
    await session.flush()
    session.add(RoleAssignment(user_id=admin_uuid, role_id=role.id, assigned_by=admin_uuid))
    session.add(PIIAuditLog(conversation_id=conv1.id, mask_count=2, pii_types=["phone", "email"], action="mask", performed_by=user_uuid))
    
    await session.commit()

@pytest.mark.asyncio
async def test_all_13_odd_sql_queries(db_session):
    await seed_data(db_session)
    
    # --- Phase 1 SQLs ---
    
    # 1. FCR Calculation
    fcr_sql = """
    SELECT ROUND(SUM(CASE WHEN knowledge_source = 'rule' AND confidence >= 0.7 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 2)
    FROM messages WHERE role = 'assistant';
    """
    res = (await db_session.execute(text(fcr_sql))).fetchone()
    # 1 rule match out of 3 assistant msgs = 33.33%
    assert float(res[0]) == 33.33

    # 2. p95 Latency
    latency_sql = "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) FROM messages WHERE role = 'assistant';"
    res = (await db_session.execute(text(latency_sql))).fetchone()
    assert float(res[0]) > 0

    # 3. Knowledge Match Distribution
    dist_sql = "SELECT knowledge_source, COUNT(*) FROM messages WHERE role = 'assistant' GROUP BY knowledge_source;"
    rows = (await db_session.execute(text(dist_sql))).fetchall()
    assert len(rows) == 3 # rule, rag, escalate

    # --- Phase 2 SQLs ---

    # 4. CSAT Score
    csat_sql = "SELECT AVG(satisfaction_score) FROM conversations WHERE satisfaction_score IS NOT NULL;"
    res = (await db_session.execute(text(csat_sql))).fetchone()
    assert float(res[0]) == 4.5 # (5+4)/2

    # 5. Knowledge Match Distribution (%)
    dist_pct_sql = """
    SELECT knowledge_source, COUNT(*), ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM messages WHERE role = 'assistant' GROUP BY knowledge_source;
    """
    rows = (await db_session.execute(text(dist_pct_sql))).fetchall()
    assert any(r[0] == 'rag' and float(r[2]) == 33.33 for r in rows)

    # 6. Escalation SLA Adherence
    sla_sql = """
    SELECT priority, SUM(CASE WHEN resolved_at <= sla_deadline THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
    FROM escalation_queue GROUP BY priority;
    """
    res = (await db_session.execute(text(sla_sql))).fetchone()
    assert float(res[1]) == 100.0

    # 7. Emotion Trigger Stats
    emotion_sql = "SELECT category, COUNT(*), AVG(intensity) FROM emotion_history GROUP BY category;"
    rows = (await db_session.execute(text(emotion_sql))).fetchall()
    assert len(rows) == 2

    # 8. Security Blocking Rate (L3)
    block_sql = "SELECT SUM(CASE WHEN blocked THEN 1 ELSE 0 END) * 100.0 / COUNT(*) FROM security_logs WHERE layer = 'L3';"
    res = (await db_session.execute(text(block_sql))).fetchone()
    assert float(res[0]) == 50.0

    # --- Phase 3 SQLs ---

    # 9. Cost per Resolution
    cost_res_sql = "SELECT SUM(resolution_cost) / NULLIF(COUNT(CASE WHEN first_contact_resolution THEN 1 END), 0) FROM conversations;"
    res = (await db_session.execute(text(cost_res_sql))).fetchone()
    # Total cost = 0.1+0.5+2.0 = 2.6. Total FCR = 2. 2.6 / 2 = 1.3
    assert float(res[0]) == 1.3

    # 10. Monthly Cost Report
    cost_report_sql = """
    SELECT knowledge_source, COUNT(*),
      CASE knowledge_source WHEN 'rag' THEN COUNT(*) * 0.003
                             WHEN 'wiki' THEN COUNT(*) * 0.009
                             ELSE 0 END AS cost
    FROM messages GROUP BY knowledge_source;
    """
    rows = (await db_session.execute(text(cost_report_sql))).fetchall()
    assert any(r[0] == 'rag' and float(r[2]) > 0 for r in rows)

    # 11. PII Audit
    pii_audit_sql = "SELECT SUM(mask_count) FROM pii_audit_log;"
    res = (await db_session.execute(text(pii_audit_sql))).fetchone()
    assert int(res[0]) == 2

    # 12. RBAC Audit
    rbac_audit_sql = "SELECT u.platform_user_id, r.name FROM role_assignments ra JOIN users u ON ra.user_id = u.unified_user_id JOIN roles r ON ra.role_id = r.id;"
    res = (await db_session.execute(text(rbac_audit_sql))).fetchone()
    assert res[1] == "admin"

    # 13. A/B Experiment Effects
    ab_effect_sql = "SELECT e.name, er.variant, er.metric_value FROM experiment_results er JOIN experiments e ON er.experiment_id = e.id WHERE e.status = 'running';"
    res = (await db_session.execute(text(ab_effect_sql))).fetchone()
    assert res[1] == "test"
    assert float(res[2]) == 0.85
