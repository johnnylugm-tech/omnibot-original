import pytest
import pytest_asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker
from app.models.database import Base, User, Conversation, Message, KnowledgeBase, EscalationQueue, Experiment, Role, RoleAssignment, PIIAuditLog
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
    # 1. Create User
    user_uuid = uuid.uuid4()
    user = User(unified_user_id=user_uuid, platform="telegram", platform_user_id="123")
    session.add(user)
    await session.flush() # Ensure user is persisted for FK
    
    # 2. Conversations & Messages
    # Conv 1: Resolved by Rule (FCR pass)
    conv1 = Conversation(unified_user_id=user_uuid, platform="telegram", first_contact_resolution=True, resolution_cost=0.0)
    session.add(conv1)
    await session.flush()
    
    msg1_u = Message(conversation_id=conv1.id, role="user", content="hello")
    msg1_a = Message(conversation_id=conv1.id, role="assistant", content="world", knowledge_source="rule", confidence=0.95)
    session.add_all([msg1_u, msg1_a])
    
    # Conv 2: Escalated (FCR fail)
    conv2 = Conversation(unified_user_id=user_uuid, platform="telegram", first_contact_resolution=False, resolution_cost=1.0)
    session.add(conv2)
    await session.flush()
    
    msg2_u = Message(conversation_id=conv2.id, role="user", content="help")
    msg2_a = Message(conversation_id=conv2.id, role="assistant", content="transferring", knowledge_source="escalate", confidence=0.0)
    session.add_all([msg2_u, msg2_a])
    
    # 3. Escalation Queue (for SLA)
    deadline = datetime.utcnow() + timedelta(minutes=30)
    session.add(EscalationQueue(conversation_id=conv2.id, reason="unresolved", priority=3, sla_deadline=deadline, resolved_at=datetime.utcnow()))
    
    # 4. Experiments
    exp = Experiment(name="test_v1", status="running", variants={}, traffic_split={"control": 50, "test": 50})
    session.add(exp)
    
    # 5. Roles & PII logs
    role = Role(name="admin", permissions={})
    session.add(role)
    await session.flush()
    session.add(RoleAssignment(user_id=user_uuid, role_id=role.id))
    session.add(PIIAuditLog(conversation_id=conv1.id, mask_count=2, pii_types=["phone"], action="mask", performed_by=user_uuid))
    
    await session.commit()

@pytest.mark.asyncio
async def test_odd_sql_phase1_fcr(db_session):
    await seed_data(db_session)
    
    # SQL 1: FCR Calculation
    sql = """
    SELECT
      ROUND(
        SUM(CASE WHEN knowledge_source = 'rule' AND confidence >= 0.7 THEN 1 ELSE 0 END)
        * 100.0 / NULLIF(COUNT(*), 0), 2
      ) AS fcr_pct
    FROM messages WHERE role = 'assistant';
    """
    result = await db_session.execute(text(sql))
    row = result.fetchone()
    assert float(row[0]) == 50.0

@pytest.mark.asyncio
async def test_odd_sql_phase2_sla(db_session):
    await seed_data(db_session)
    
    # SQL 2: SLA Adherence
    sql = """
    SELECT priority,
      SUM(CASE WHEN resolved_at <= sla_deadline THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
    FROM escalation_queue GROUP BY priority;
    """
    result = await db_session.execute(text(sql))
    row = result.fetchone()
    assert row[0] == 3
    assert float(row[1]) == 100.0

@pytest.mark.asyncio
async def test_odd_sql_phase3_cost(db_session):
    await seed_data(db_session)
    
    # SQL 3: Cost per Resolution
    sql = """
    SELECT SUM(resolution_cost) / NULLIF(COUNT(CASE WHEN first_contact_resolution THEN 1 END), 0)
    FROM conversations;
    """
    result = await db_session.execute(text(sql))
    row = result.fetchone()
    assert float(row[0]) == 1.0
