import pytest
import pytest_asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from app.models.database import Base

# Use environment variable or default to localhost
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://omnibot:password@localhost:5433/omnibot")

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(DATABASE_URL)
    
    # Initialize schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield engine
    await engine.dispose()

@pytest.mark.asyncio
async def test_verify_all_tables_exist(db_engine: AsyncEngine):
    expected_tables = {
        # Phase 1
        "users", "conversations", "messages", "knowledge_base",
        "platform_configs", "escalation_queue", "user_feedback", "security_logs",
        # Phase 2
        "emotion_history", "edge_cases",
        # Phase 3
        "roles", "role_assignments", "pii_audit_log", "experiments",
        "experiment_results", "retry_log", "encryption_config", "schema_migrations"
    }
    
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        existing_tables = {row[0] for row in result.fetchall()}
        
        missing_tables = expected_tables - existing_tables
        assert not missing_tables, f"Missing tables in database: {missing_tables}"
        assert len(existing_tables.intersection(expected_tables)) >= 18

@pytest.mark.asyncio
async def test_verify_knowledge_base_columns(db_engine: AsyncEngine):
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'knowledge_base' AND column_name = 'embeddings'
            """)
        )
        row = result.fetchone()
        assert row is not None
        # In our SQLAlchemy model, it's JSONB
        assert row[1] in ["jsonb", "USER-DEFINED"] 
