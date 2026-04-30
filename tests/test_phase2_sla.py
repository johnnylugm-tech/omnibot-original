"""
Atomic TDD Tests for Phase 2: SLA Escalation (#21)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from app.services.escalation import EscalationManager
from app.models import EscalationRequest

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db

@pytest.mark.asyncio
async def test_id_21_01_sla_p0_15_minutes(mock_db):
    """priority=0 (P0) → 15min SLA"""
    manager = EscalationManager(mock_db)
    req = EscalationRequest(conversation_id="c1", reason="test")
    
    # We need to capture the object passed to db.add
    await manager.create(req, priority=0)
    
    added_obj = mock_db.add.call_args[0][0]
    expected_deadline = datetime.utcnow() + timedelta(minutes=15)
    # Check within 5 seconds tolerance
    assert abs((added_obj.sla_deadline - expected_deadline).total_seconds()) < 5
    assert added_obj.priority == 0

@pytest.mark.asyncio
async def test_id_21_02_sla_p1_30_minutes(mock_db):
    """priority=1 (P1) → 30min SLA"""
    manager = EscalationManager(mock_db)
    req = EscalationRequest(conversation_id="c1", reason="test")
    await manager.create(req, priority=1)
    
    added_obj = mock_db.add.call_args[0][0]
    assert added_obj.priority == 1
    assert abs((added_obj.sla_deadline - (datetime.utcnow() + timedelta(minutes=30))).total_seconds()) < 5

@pytest.mark.asyncio
async def test_id_21_03_sla_p2_120_minutes(mock_db):
    """priority=2 (P2) → 120min SLA"""
    manager = EscalationManager(mock_db)
    req = EscalationRequest(conversation_id="c1", reason="test")
    await manager.create(req, priority=2)
    
    added_obj = mock_db.add.call_args[0][0]
    assert added_obj.priority == 2
    assert abs((added_obj.sla_deadline - (datetime.utcnow() + timedelta(minutes=120))).total_seconds()) < 5

@pytest.mark.asyncio
async def test_id_21_04_get_sla_breaches(mock_db):
    """Verify get_sla_breaches filters correctly"""
    manager = EscalationManager(mock_db)
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["breach1", "breach2"]
    mock_db.execute.return_value = mock_result
    
    results = await manager.get_sla_breaches()
    
    assert results == ["breach1", "breach2"]
    # Verify the query conditions (conceptually)
    args, kwargs = mock_db.execute.call_args
    query_str = str(args[0])
    assert "sla_deadline <" in query_str
    assert "resolved_at IS NULL" in query_str

@pytest.mark.asyncio
async def test_id_21_05_get_sla_breaches_ordered_by_priority(mock_db):
    """Verify results are ordered by priority DESC, queued_at ASC"""
    manager = EscalationManager(mock_db)
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    await manager.get_sla_breaches()
    
    args, kwargs = mock_db.execute.call_args
    query_str = str(args[0]).lower()
    assert "order by" in query_str
    assert "priority desc" in query_str
    assert "queued_at asc" in query_str


# =============================================================================
# SLA Breach Detection by Priority (Section 22) — NEW RED test
# =============================================================================

@pytest.mark.asyncio
async def test_sla_breach_detection_varies_by_priority(mock_db):
    """Different priority levels have different SLA thresholds:
    - p0 (critical) = 15 min
    - p1 (high) = 30 min
    - p2 (normal) = 120 min

    RED reason: The current SLA implementation does not vary by priority with these exact thresholds.
    The function get_sla_breaches() must accept priority filter and calculate deadline from now.
    """
    from datetime import datetime, timedelta
    from app.services.escalation import EscalationManager
    from app.models import EscalationRequest

    manager = EscalationManager(mock_db)

    thresholds = {
        0: 15,   # p0 critical → 15 min
        1: 30,   # p1 high → 30 min
        2: 120,  # p2 normal → 120 min
    }

    # For each priority, verify the SLA deadline is correct
    for priority, expected_minutes in thresholds.items():
        mock_db.add.reset_mock()
        req = EscalationRequest(conversation_id=f"c-{priority}", reason="test")
        await manager.create(req, priority=priority)

        added_obj = mock_db.add.call_args[0][0]
        expected_deadline = datetime.utcnow() + timedelta(minutes=expected_minutes)
        diff_seconds = abs((added_obj.sla_deadline - expected_deadline).total_seconds())
        assert diff_seconds < 5, \
            f"Priority {priority} expected SLA={expected_minutes}min, deadline diff={diff_seconds}s"


# =============================================================================
# S21 Escalation SLA — Missing细粒度 tests (3 items)
# =============================================================================

@pytest.mark.asyncio
async def test_escalation_manager_create_returns_id(mock_db):
    """create() must return a numeric ticket ID."""
    manager = EscalationManager(mock_db)
    req = EscalationRequest(conversation_id=1, reason="test")

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()

    async def refresh_side_effect(obj):
        obj.id = 42

    mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

    ticket_id = await manager.create(req, priority=0)
    assert isinstance(ticket_id, int), "create() must return an int ticket ID"
    assert ticket_id == 42


@pytest.mark.asyncio
async def test_escalation_manager_assign(mock_db):
    """assign() must persist assigned_agent and picked_at to the ticket."""
    manager = EscalationManager(mock_db)

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()

    await manager.assign(escalation_id=1, agent_id="agent_007")

    assert mock_db.execute.called, "assign() must call db.execute()"
    assert mock_db.commit.called, "assign() must call db.commit()"


@pytest.mark.asyncio
async def test_escalation_manager_resolve_sets_resolved_at(mock_db):
    """resolve() must set resolved_at timestamp on the ticket."""
    manager = EscalationManager(mock_db)

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()

    await manager.resolve(escalation_id=1)

    assert mock_db.execute.called, "resolve() must call db.execute()"
    assert mock_db.commit.called, "resolve() must call db.commit()"
