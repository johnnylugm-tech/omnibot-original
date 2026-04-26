"""SQLAlchemy models and database schema"""
import os
from datetime import datetime
from typing import Any, AsyncGenerator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://omnibot:password@localhost:5432/omnibot")
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting DB session"""
    async with AsyncSessionLocal() as session:
        yield session


class Base(DeclarativeBase):
    pass


class User(Base):
    """Cross-platform user table"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    unified_user_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=lambda: __import__('uuid').uuid4())
    platform = Column(String(20), nullable=False)
    platform_user_id = Column(String(100), nullable=False)
    profile = Column(JSONB)
    preference_tags: Any = Column(ARRAY(Text))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('platform', 'platform_user_id', name='uq_platform_user'),
    )


class Conversation(Base):
    """Conversation history"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    unified_user_id = Column(UUID(as_uuid=True), ForeignKey('users.unified_user_id'))
    platform = Column(String(20), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    status = Column(String(20), default='active')
    satisfaction_score = Column(Float)
    first_contact_resolution = Column(Boolean)
    resolution_cost = Column(Float)
    response_time_ms = Column(Integer)
    scope_type = Column(String(20), default='in_scope')
    dst_state = Column(JSONB)

    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    """Message records"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'))
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    intent_detected = Column(String(50))
    sentiment_category = Column(String(20))
    sentiment_intensity = Column(Float)
    confidence_score = Column(Float)
    knowledge_source = Column(String(20))
    user_feedback = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class KnowledgeBase(Base):
    """Knowledge base with vector support (Phase 2)"""
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True)
    category = Column(String(50), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    keywords: Any = Column(ARRAY(Text))  # type: ignore
    embeddings = Column(JSONB)  # vector(384) - Phase 2 with pgvector
    embedding_model = Column(String(100), default='paraphrase-multilingual-MiniLM-L12-v2')
    version = Column(Integer, default=1)
    contains_pii = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlatformConfig(Base):
    """Platform adapter configuration"""
    __tablename__ = "platform_configs"

    platform = Column(String(20), primary_key=True)
    enabled = Column(Boolean, default=True)
    config = Column(JSONB)
    rate_limit_rps = Column(Integer, default=100)
    max_session_duration_sec = Column(Integer, default=1800)
    webhook_secret_key_ref = Column(String(100))
    updated_at = Column(DateTime, default=datetime.utcnow)


class EscalationQueue(Base):
    """Human escalation queue (Phase 1 no SLA)"""
    __tablename__ = "escalation_queue"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), unique=True)
    reason = Column(String(50), nullable=False)
    priority = Column(Integer, default=0)
    assigned_agent = Column(UUID(as_uuid=True), ForeignKey('users.unified_user_id'))
    queued_at = Column(DateTime, default=datetime.utcnow)
    picked_at = Column(DateTime)
    resolved_at = Column(DateTime)
    sla_deadline = Column(DateTime)


class UserFeedback(Base):
    """User feedback collection"""
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'))
    message_id = Column(Integer, ForeignKey('messages.id'))
    feedback = Column(String(20), nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SecurityLog(Base):
    """Security event logs"""
    __tablename__ = "security_logs"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'))
    layer = Column(String(10), nullable=False)
    blocked = Column(Boolean, default=False)
    block_reason = Column(Text)
    source_ip = Column(String(45))
    platform = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)


# SQL Schema (for direct execution without ORM)
SCHEMA_SQL = """
-- Users table (cross-platform)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    unified_user_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    platform VARCHAR(20) NOT NULL,
    platform_user_id VARCHAR(100) NOT NULL,
    profile JSONB,
    preference_tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(platform, platform_user_id)
);

CREATE INDEX IF NOT EXISTS idx_users_platform_uid ON users (platform, platform_user_id);

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    unified_user_id UUID REFERENCES users(unified_user_id),
    platform VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    satisfaction_score FLOAT,
    first_contact_resolution BOOLEAN,
    resolution_cost FLOAT,
    response_time_ms INTEGER,
    scope_type VARCHAR(20) DEFAULT 'in_scope',
    dst_state JSONB
);

CREATE INDEX IF NOT EXISTS idx_conversations_started ON conversations (started_at);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations (unified_user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_platform ON conversations (platform, started_at);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    intent_detected VARCHAR(50),
    sentiment_category VARCHAR(20),
    sentiment_intensity FLOAT,
    confidence_score FLOAT,
    knowledge_source VARCHAR(20),
    user_feedback VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages (created_at);

-- Knowledge base
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    keywords TEXT[],
    embeddings JSONB,
    embedding_model VARCHAR(100) DEFAULT 'paraphrase-multilingual-MiniLM-L12-v2',
    version INTEGER DEFAULT 1,
    contains_pii BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base (category);
CREATE INDEX IF NOT EXISTS idx_kb_keywords ON knowledge_base USING GIN (keywords);

-- Platform configs
CREATE TABLE IF NOT EXISTS platform_configs (
    platform VARCHAR(20) PRIMARY KEY,
    enabled BOOLEAN DEFAULT TRUE,
    config JSONB,
    rate_limit_rps INTEGER DEFAULT 100,
    max_session_duration_sec INTEGER DEFAULT 1800,
    webhook_secret_key_ref VARCHAR(100),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Escalation queue
CREATE TABLE IF NOT EXISTS escalation_queue (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) UNIQUE,
    reason VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 0,
    assigned_agent UUID REFERENCES users(unified_user_id),
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    picked_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    sla_deadline TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_escalation_pending ON escalation_queue (queued_at) WHERE resolved_at IS NULL;

-- User feedback
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    message_id INTEGER REFERENCES messages(id),
    feedback VARCHAR(20) NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Security logs
CREATE TABLE IF NOT EXISTS security_logs (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    layer VARCHAR(10) NOT NULL,
    blocked BOOLEAN DEFAULT FALSE,
    block_reason TEXT,
    source_ip INET,
    platform VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_logs_date ON security_logs (created_at);
"""
