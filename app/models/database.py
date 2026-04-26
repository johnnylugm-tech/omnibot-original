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


class EmotionHistory(Base):
    """Historical emotion scores for decay calculation (Phase 2)"""
    __tablename__ = "emotion_history"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    category = Column(String(20), nullable=False)
    intensity = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class EdgeCase(Base):
    """Tracking for grounding failures and unusual inputs (Phase 2)"""
    __tablename__ = "edge_cases"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'))
    message_id = Column(Integer, ForeignKey('messages.id'))
    case_type = Column(String(50), nullable=False)  # grounding_fail | unusual_input
    raw_content = Column(Text)
    llm_output = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SchemaMigration(Base):
    """Tracking schema versions (Phase 3)"""
    __tablename__ = "schema_migrations"

    version = Column(String(20), primary_key=True)
    description = Column(Text, nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow)
    checksum = Column(String(64), nullable=False)


class Role(Base):
    """RBAC Role definitions"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    permissions = Column(JSONB, nullable=False)  # Map of resource -> actions
    created_at = Column(DateTime, default=datetime.utcnow)


class RoleAssignment(Base):
    """User-to-Role assignments"""
    __tablename__ = "role_assignments"

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.unified_user_id'))
    role_id = Column(Integer, ForeignKey('roles.id'))
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey('users.unified_user_id'))

    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
    )


class PIIAuditLog(Base):
    """Audit logs for PII masking actions"""
    __tablename__ = "pii_audit_log"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'))
    mask_count = Column(Integer, nullable=False)
    pii_types = Column(ARRAY(Text))
    action = Column(String(20), nullable=False)
    performed_by = Column(UUID(as_uuid=True), ForeignKey('users.unified_user_id'))
    created_at = Column(DateTime, default=datetime.utcnow)


class Experiment(Base):
    """A/B Testing experiments"""
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    variants = Column(JSONB, nullable=False)  # Variant config
    traffic_split = Column(JSONB, nullable=False)  # Split percentages
    status = Column(String(20), default='draft')  # draft | running | completed | aborted
    started_at = Column(DateTime)
    ended_at = Column(DateTime)


class ExperimentResult(Base):
    """A/B Testing results"""
    __tablename__ = "experiment_results"

    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey('experiments.id'))
    variant = Column(String(50), nullable=False)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RetryLog(Base):
    """Log of retried operations"""
    __tablename__ = "retry_log"

    id = Column(Integer, primary_key=True)
    operation = Column(String(100), nullable=False)
    attempt_count = Column(Integer, nullable=False)
    delay_seconds = Column(Float)
    error_message = Column(Text)
    status = Column(String(20), nullable=False)
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

-- RBAC Roles
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Role Assignments
CREATE TABLE IF NOT EXISTS role_assignments (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(unified_user_id),
    role_id INTEGER REFERENCES roles(id),
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by UUID REFERENCES users(unified_user_id),
    UNIQUE(user_id, role_id)
);

-- PII Audit Log
CREATE TABLE IF NOT EXISTS pii_audit_log (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    mask_count INTEGER NOT NULL,
    pii_types TEXT[],
    action VARCHAR(20) NOT NULL,
    performed_by UUID REFERENCES users(unified_user_id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pii_audit_date ON pii_audit_log (created_at);

-- A/B Testing Experiments
CREATE TABLE IF NOT EXISTS experiments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    variants JSONB NOT NULL,
    traffic_split JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'draft'
        CHECK (status IN ('draft', 'running', 'completed', 'aborted')),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ
);

-- Experiment Results
CREATE TABLE IF NOT EXISTS experiment_results (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER REFERENCES experiments(id),
    variant VARCHAR(50) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value FLOAT NOT NULL,
    sample_size INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Retry Logs
CREATE TABLE IF NOT EXISTS retry_log (
    id SERIAL PRIMARY KEY,
    operation VARCHAR(100) NOT NULL,
    attempt_count INTEGER NOT NULL,
    delay_seconds FLOAT,
    error_message TEXT,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""
