import pytest
import pytest_asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker
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
    # Create Users
    admin_uuid = uuid.uuid4()
    user_uuid = uuid.uuid4()
    session.add_all([
        User(unified_user_id=admin_uuid, platform="system", platform_user_id="admin"),
        User(unified_user_id=user_uuid, platform="telegram", platform_user_id="123")
    ])
    await session.flush()
    
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
    
    # Conv 2: Resolved by RAG
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
    
    # Conv 3: Escalated
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
    
    # Escalation Queue
    session.add(EscalationQueue(
        conversation_id=conv3.id, reason="manual_request", priority=3, 
        sla_deadline=datetime.utcnow() + timedelta(minutes=5),
        resolved_at=datetime.utcnow()
    ))
    
    # Emotion History
    session.add_all([
        EmotionHistory(conversation_id=conv3.id, category="NEGATIVE", intensity=0.9),
        EmotionHistory(conversation_id=conv1.id, category="POSITIVE", intensity=0.8)
    ])
    
    # Security Logs
    session.add_all([
        SecurityLog(conversation_id=conv1.id, layer="L3", blocked=True, block_reason="injection"),
        SecurityLog(conversation_id=conv2.id, layer="L3", blocked=False)
    ])
    
    # Experiments
    exp = Experiment(name="prompt_v2", status="running", variants={}, traffic_split={"control": 50, "test": 50})
    session.add(exp)
    await session.flush()
    session.add(ExperimentResult(experiment_id=exp.id, variant="test", metric_name="fcr", metric_value=0.85, sample_size=100))
    
    # Roles & PII logs
    role = Role(name="admin", permissions={"knowledge": ["read", "write"]})
    session.add(role)
    await session.flush()
    session.add(RoleAssignment(user_id=admin_uuid, role_id=role.id, assigned_by=admin_uuid))
    session.add(PIIAuditLog(conversation_id=conv1.id, mask_count=2, pii_types=["phone", "email"], action="mask", performed_by=user_uuid))
    
    await session.commit()

# --- 13 ODD SQL Tests ---

@pytest.mark.asyncio
async def test_odd_sql_1_fcr(db_session):
    await seed_data(db_session)
    sql = "SELECT ROUND(SUM(CASE WHEN knowledge_source = 'rule' AND confidence >= 0.7 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 2) FROM messages WHERE role = 'assistant';"
    res = (await db_session.execute(text(sql))).fetchone()
    assert float(res[0]) == 33.33

@pytest.mark.asyncio
async def test_odd_sql_2_latency(db_session):
    await seed_data(db_session)
    sql = "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) FROM messages WHERE role = 'assistant';"
    res = (await db_session.execute(text(sql))).fetchone()
    assert float(res[0]) > 0

@pytest.mark.asyncio
async def test_odd_sql_3_knowledge_distribution(db_session):
    await seed_data(db_session)
    sql = "SELECT knowledge_source, COUNT(*) FROM messages WHERE role = 'assistant' GROUP BY knowledge_source;"
    rows = (await db_session.execute(text(sql))).fetchall()
    assert len(rows) == 3

@pytest.mark.asyncio
async def test_odd_sql_4_csat(db_session):
    await seed_data(db_session)
    sql = "SELECT AVG(satisfaction_score) FROM conversations WHERE satisfaction_score IS NOT NULL;"
    res = (await db_session.execute(text(sql))).fetchone()
    assert float(res[0]) == 4.5

@pytest.mark.asyncio
async def test_odd_sql_5_knowledge_dist_pct(db_session):
    await seed_data(db_session)
    sql = "SELECT knowledge_source, COUNT(*), ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct FROM messages WHERE role = 'assistant' GROUP BY knowledge_source;"
    rows = (await db_session.execute(text(sql))).fetchall()
    assert any(r[0] == 'rag' and float(r[2]) == 33.33 for r in rows)

@pytest.mark.asyncio
async def test_odd_sql_6_sla_adherence(db_session):
    await seed_data(db_session)
    sql = "SELECT priority, SUM(CASE WHEN resolved_at <= sla_deadline THEN 1 ELSE 0 END) * 100.0 / COUNT(*) FROM escalation_queue GROUP BY priority;"
    res = (await db_session.execute(text(sql))).fetchone()
    assert float(res[1]) == 100.0

@pytest.mark.asyncio
async def test_odd_sql_7_emotion_stats(db_session):
    await seed_data(db_session)
    sql = "SELECT category, COUNT(*), AVG(intensity) FROM emotion_history GROUP BY category;"
    rows = (await db_session.execute(text(sql))).fetchall()
    assert len(rows) == 2

@pytest.mark.asyncio
async def test_odd_sql_8_blocking_rate(db_session):
    await seed_data(db_session)
    sql = "SELECT SUM(CASE WHEN blocked THEN 1 ELSE 0 END) * 100.0 / COUNT(*) FROM security_logs WHERE layer = 'L3';"
    res = (await db_session.execute(text(sql))).fetchone()
    assert float(res[0]) == 50.0

@pytest.mark.asyncio
async def test_odd_sql_9_cost_per_res(db_session):
    await seed_data(db_session)
    sql = "SELECT SUM(resolution_cost) / NULLIF(COUNT(CASE WHEN first_contact_resolution THEN 1 END), 0) FROM conversations;"
    res = (await db_session.execute(text(sql))).fetchone()
    assert float(res[0]) == 1.3

@pytest.mark.asyncio
async def test_odd_sql_10_monthly_cost(db_session):
    await seed_data(db_session)
    sql = "SELECT knowledge_source, COUNT(*), CASE knowledge_source WHEN 'rag' THEN COUNT(*) * 0.003 WHEN 'wiki' THEN COUNT(*) * 0.009 ELSE 0 END AS cost FROM messages GROUP BY knowledge_source;"
    rows = (await db_session.execute(text(sql))).fetchall()
    assert any(r[0] == 'rag' and float(r[2]) > 0 for r in rows)

@pytest.mark.asyncio
async def test_odd_sql_11_pii_audit(db_session):
    await seed_data(db_session)
    sql = "SELECT SUM(mask_count) FROM pii_audit_log;"
    res = (await db_session.execute(text(sql))).fetchone()
    assert int(res[0]) == 2

@pytest.mark.asyncio
async def test_odd_sql_12_rbac_audit(db_session):
    await seed_data(db_session)
    sql = "SELECT u.platform_user_id, r.name FROM role_assignments ra JOIN users u ON ra.user_id = u.unified_user_id JOIN roles r ON ra.role_id = r.id;"
    res = (await db_session.execute(text(sql))).fetchone()
    assert res[1] == "admin"

@pytest.mark.asyncio
async def test_odd_sql_13_ab_experiment(db_session):
    await seed_data(db_session)
    sql = "SELECT e.name, er.variant, er.metric_value FROM experiment_results er JOIN experiments e ON er.experiment_id = e.id WHERE e.status = 'running';"
    res = (await db_session.execute(text(sql))).fetchone()
    assert res[1] == "test"
    assert float(res[2]) == 0.85
