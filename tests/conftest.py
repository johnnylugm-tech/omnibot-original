"""Shared pytest fixtures and mocks for omnibot test suite."""
import sys
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

import pytest

# -----------------------------------------------------------------------
# Stub non-existent production modules so test imports don't hard-crash.
# Each stub provides the minimum API surface that the corresponding
# test file expects.
# -----------------------------------------------------------------------

def _make_alerts_stub():
    """Return a fake app.utils.alerts module."""
    mod = MagicMock()
    mod.AlertManager = MagicMock()
    mod.AlertCondition = MagicMock()
    mod.AlertRule = MagicMock()
    # Provide async methods that return immediately
    instance = MagicMock()
    instance.check_error_rate = AsyncMock(return_value=False)
    instance.check_sla_breach = AsyncMock(return_value=False)
    instance.check_grounding_rate = AsyncMock(return_value=False)
    instance._trigger_alert = AsyncMock(return_value=None)
    instance.fire_webhook = AsyncMock(return_value=None)
    mod.AlertManager.return_value = instance
    return mod

def _make_backup_stub():
    """Return a fake app.services.backup module."""
    mod = MagicMock()
    mod.BackupService = MagicMock()
    instance = MagicMock()
    instance.create_backup = AsyncMock(return_value={"id": 1, "status": "completed"})
    instance.schedule_next_backup = AsyncMock(
        return_value=datetime.utcnow() + timedelta(hours=24)
    )
    instance.cleanup_old_backups = AsyncMock(return_value=None)
    instance.get_backup_status = MagicMock(
        return_value={"id": 1, "status": "completed", "created_at": datetime.utcnow()}
    )
    mod.BackupService.return_value = instance
    return mod

def _make_degradation_stub():
    """Return a fake app.services.degradation module."""
    mod = MagicMock()
    mod.DegradationManager = MagicMock()
    instance = MagicMock()
    instance.detect_llm_timeout = AsyncMock(return_value=False)
    instance.fallback_to_knowledge = AsyncMock(return_value={"source": "knowledge_base"})
    instance.circuit_open = False
    instance.circuit_half_open = False
    instance.activate_degraded = AsyncMock(return_value=None)
    instance.recover = AsyncMock(return_value=None)
    instance.get_status = MagicMock(return_value={"mode": "normal"})
    mod.DegradationManager.return_value = instance
    return mod

def _make_cost_model_stub():
    """Return a fake app.utils.cost_model module."""
    mod = MagicMock()
    mod.CostModel = MagicMock()
    instance = MagicMock()
    instance.calculate_cost = MagicMock(return_value=0.001)
    instance.check_budget = MagicMock(return_value={"within_budget": True})
    instance.log_cost = MagicMock(return_value=None)
    mod.CostModel.return_value = instance
    return mod

def _make_odd_queries_stub():
    """Return a fake app.services.odd_queries module."""
    mod = MagicMock()
    mod.ODDQueryManager = MagicMock()
    instance = MagicMock()
    instance.count = MagicMock(return_value=0)
    instance.filter_by = MagicMock(return_value=[])
    instance.paginate = MagicMock(return_value={"items": [], "total": 0})
    mod.ODDQueryManager.return_value = instance
    return mod

def _make_kpi_stub():
    """Return a fake app.services.kpi module."""
    mod = MagicMock()
    mod.KPIManager = MagicMock()
    instance = MagicMock()
    instance.get_total_conversations = MagicMock(return_value=0)
    instance.get_avg_resolution_time = MagicMock(return_value=0.0)
    instance.get_escalation_rate = MagicMock(return_value=0.0)
    instance.get_knowledge_hit_rate = MagicMock(return_value=0.0)
    instance.get_sla_compliance_rate = MagicMock(return_value=0.0)
    instance.get_revenue_per_conversation = MagicMock(return_value=0.0)
    instance.get_daily_breakdown = MagicMock(return_value=[])
    mod.KPIManager.return_value = instance
    return mod

# Install stubs into sys.modules before any test file tries to import
# sys.modules["app.utils.alerts"] = _make_alerts_stub()
# sys.modules["app.services.backup"] = _make_backup_stub()
# sys.modules["app.services.degradation"] = _make_degradation_stub() (Removed as real module exists)
# sys.modules["app.utils.cost_model"] = _make_cost_model_stub()
# sys.modules["app.services.odd_queries"] = _make_odd_queries_stub() (Removed)
@pytest.fixture
def mock_backup_service():
    """Mock for BackupService."""
    with patch("app.services.backup.BackupService") as mock:
        instance = mock.return_value
        instance.create_backup = AsyncMock(return_value={"id": 1, "status": "completed"})
        instance.schedule_next_backup = AsyncMock(
            return_value=datetime.utcnow() + timedelta(hours=24)
        )
        instance.cleanup_old_backups = AsyncMock(return_value=None)
        instance.get_backup_status = MagicMock(
            return_value={"id": 1, "status": "completed", "created_at": datetime.utcnow()}
        )
        yield instance

@pytest.fixture
def rbac_token():
    """Helper to generate signed tokens for RBAC tests."""
    from app.security.rbac import rbac
    return rbac.create_token

@pytest.fixture
def mock_db():
    """Database session mock with correct sync/async method types."""
    db = MagicMock()
    db.add = MagicMock()
    db.refresh = AsyncMock() # SQLAlchemy refresh is often used with await in async sessions
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    """Async mock for Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.xreadgroup = AsyncMock(return_value=[])
    redis.xack = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_http_client():
    """Async mock for HTTP client (httpx / aiohttp)."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    return client
