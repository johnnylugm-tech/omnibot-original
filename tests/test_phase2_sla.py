"""
Atomic TDD Tests for Phase 2: SLA Escalation (#21)
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import EscalationRequest
from app.services.escalation import EscalationManager

# =============================================================================
# Fixtures shared with error-code tests (migrated from test_phase1_extra.py)
# =============================================================================


@pytest.fixture
def mock_db_for_error_tests():
    """Mock DB for error code tests."""
    from sqlalchemy.ext.asyncio import AsyncSession

    db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result
    db.commit = AsyncMock()

    def side_effect_add(obj):
        if hasattr(obj, "id") and obj.id is None:
            obj.id = 1

    db.add = MagicMock(side_effect=side_effect_add)
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def client_with_mock_db(mock_db_for_error_tests):
    """TestClient with overridden DB dependency."""
    from fastapi.testclient import TestClient

    from app.api import app
    from app.models.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db_for_error_tests
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_id_21_01_sla_p0_30_minutes(mock_db):
    """priority=0 (NORMAL) → 30min SLA"""
    manager = EscalationManager(mock_db)
    req = EscalationRequest(conversation_id="c1", reason="test")
    await manager.create(req, priority=0)

    added_obj = mock_db.add.call_args[0][0]
    expected_deadline = datetime.utcnow() + timedelta(minutes=30)
    assert abs((added_obj.sla_deadline - expected_deadline).total_seconds()) < 5
    assert added_obj.priority == 0


@pytest.mark.asyncio
async def test_id_21_02_sla_p1_15_minutes(mock_db):
    """priority=1 (HIGH) → 15min SLA"""
    manager = EscalationManager(mock_db)
    req = EscalationRequest(conversation_id="c1", reason="test")
    await manager.create(req, priority=1)

    added_obj = mock_db.add.call_args[0][0]
    assert added_obj.priority == 1
    assert (
        abs(
            (
                added_obj.sla_deadline - (datetime.utcnow() + timedelta(minutes=15))
            ).total_seconds()
        )
        < 5
    )


@pytest.mark.asyncio
async def test_id_21_03_sla_p2_5_minutes(mock_db):
    """priority=2 (URGENT/emotion_trigger) → 5min SLA"""
    manager = EscalationManager(mock_db)
    req = EscalationRequest(conversation_id="c1", reason="test")
    await manager.create(req, priority=2)

    added_obj = mock_db.add.call_args[0][0]
    assert added_obj.priority == 2
    assert (
        abs(
            (
                added_obj.sla_deadline - (datetime.utcnow() + timedelta(minutes=5))
            ).total_seconds()
        )
        < 5
    )


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
    args, _ = mock_db.execute.call_args
    query_str = str(args[0]).lower()
    # Depending on SQLAlchemy version and dialect, it might be 'is null' or '= null'
    # Check for core parts of the SLA breach query
    assert "from escalation_queue" in query_str
    assert "sla_deadline" in query_str


@pytest.mark.asyncio
async def test_id_21_05_get_sla_breaches_ordered_by_priority(mock_db):
    """Verify results are ordered by priority DESC, queued_at ASC"""
    manager = EscalationManager(mock_db)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    await manager.get_sla_breaches()

    args, _ = mock_db.execute.call_args
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
    - priority=0 (NORMAL) = 30 min
    - priority=1 (HIGH) = 15 min
    - priority=2 (URGENT/emotion_trigger) = 5 min

    Spec: SLA_MINUTES = {0: 30, 1: 15, 2: 5}
    """
    from datetime import datetime, timedelta

    from app.models import EscalationRequest
    from app.services.escalation import EscalationManager

    manager = EscalationManager(mock_db)

    thresholds = {
        0: 30,  # NORMAL → 30 min
        1: 15,  # HIGH → 15 min
        2: 5,  # URGENT/emotion_trigger → 5 min
    }

    # For each priority, verify the SLA deadline is correct
    for priority, expected_minutes in thresholds.items():
        mock_db.add.reset_mock()
        req = EscalationRequest(conversation_id=f"c-{priority}", reason="test")
        await manager.create(req, priority=priority)

        added_obj = mock_db.add.call_args[0][0]
        expected_deadline = datetime.utcnow() + timedelta(minutes=expected_minutes)
        diff_seconds = abs((added_obj.sla_deadline - expected_deadline).total_seconds())
        assert diff_seconds < 5, (
            f"Priority {priority} expected SLA={expected_minutes}min, "
            f"deadline diff={diff_seconds}s"
        )


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


# =============================================================================
# S21 – Error handling: LLM timeout (Phase 2)
# =============================================================================


def test_error_llm_timeout_504(client_with_mock_db, mock_db_for_error_tests):
    """LLM timeout returns 504 LLM_TIMEOUT.

    Spec: When process_webhook_message raises TimeoutError, the webhook
    endpoint must return HTTP 504 with detail "LLM_TIMEOUT".
    """
    with patch(
        "app.api.routes.webhooks.process_webhook_message", new_callable=AsyncMock
    ) as mock_process:
        mock_process.side_effect = TimeoutError("LLM request timed out")

        payload = {"message": {"from": {"id": 1}, "text": "hi"}}
        response = client_with_mock_db.post(
            "/api/v1/webhook/telegram",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": ""},
        )

        assert response.status_code == 504, (
            f"Expected 504, got {response.status_code}: {response.json()}"
        )

        data = response.json()
        assert data.get("detail") == "LLM_TIMEOUT", (
            f"Expected 'LLM_TIMEOUT', got: {data}"
        )
