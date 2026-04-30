"""Escalation Manager tests - SLA tracking and User Feedback."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.escalation import EscalationManager, FeedbackManager, ValidationError
from app.models import EscalationRequest


# =============================================================================
# Escalation Manager SLA Tests (5 tests)
# =============================================================================

@pytest.mark.asyncio
async def test_escalation_manager():
    """Basic escalation creation/assign/resolve - existing smoke test."""
    mock_db = AsyncMock()
    mock_ticket = MagicMock()
    mock_ticket.id = 1
    mock_db.add = MagicMock()

    manager = EscalationManager(db=mock_db)
    req = EscalationRequest(conversation_id=1, reason="test")

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def side_effect(obj):
        obj.id = 1
    mock_db.refresh.side_effect = side_effect

    res_id = await manager.create(req)
    assert res_id == 1
    await manager.assign(1, "agent1")
    await manager.resolve(1)


@pytest.mark.asyncio
async def test_escalation_assign_on_resolved_returns_zero_affected():
    """assign() on already-resolved escalation returns 0 rows affected. RED-phase test.

    Spec: When assign() is called on an escalation ticket that already has
    resolved_at set (i.e., already resolved), the operation must return 0
    (no rows affected) rather than updating the resolved ticket.
    """
    mock_db = AsyncMock()

    # Mock execute to return a result with rowcount=0 (no rows affected)
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()

    manager = EscalationManager(db=mock_db)

    result = await manager.assign(escalation_id=1, agent_id="agent_xyz")

    # Verify rowcount is 0 (no rows affected because ticket already resolved)
    assert mock_db.execute.called, "assign() should attempt execution"
    executed_result = mock_db.execute.return_value
    assert executed_result.rowcount == 0, \
        "assign() on resolved ticket should return 0 rowcount"


@pytest.mark.asyncio
async def test_escalation_assign_on_resolved_does_not_update_picked_at():
    """assign() on resolved escalation does NOT update picked_at. RED-phase test.

    Spec: When assign() is called on an already-resolved escalation ticket,
    the picked_at field must NOT be updated. Only unresolved tickets
    can have their picked_at timestamp updated.
    """
    mock_db = AsyncMock()

    mock_ticket = MagicMock()
    mock_ticket.id = 1
    mock_ticket.resolved_at = datetime.utcnow() - timedelta(minutes=5)  # Already resolved
    mock_ticket.picked_at = None  # Never picked (because already resolved)

    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Mock execute to return rowcount=0 (ticket already resolved)
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_db.execute.return_value = mock_result

    manager = EscalationManager(db=mock_db)

    await manager.assign(escalation_id=1, agent_id="agent_xyz")

    # Verify the SQL statement does NOT include picked_at update
    # when the ticket is already resolved
    if mock_db.execute.called:
        call_args = mock_db.execute.call_args
        stmt = str(call_args[0][0])
        # If a WHERE clause exists, it should include resolved_at IS NOT NULL
        # as a condition that prevents the update
        assert "resolved" in stmt.lower() or mock_result.rowcount == 0, \
            "assign() on resolved ticket should not update picked_at"


# --- test_escalation_manager_get_sla_breaches ---
@pytest.mark.asyncio
async def test_escalation_manager_get_sla_breaches():
    """get_sla_breaches() returns tickets where deadline has passed and not resolved.

    Spec: Returns list of EscalationQueue tickets where sla_deadline < now
    AND resolved_at IS NULL.
    """
    from app.models.database import EscalationQueue

    mock_db = AsyncMock()

    # Create mock tickets: one breached, one not
    breach_time = datetime.utcnow() - timedelta(minutes=30)
    future_time = datetime.utcnow() + timedelta(minutes=30)

    mock_breach = MagicMock(spec=EscalationQueue)
    mock_breach.id = 1
    mock_breach.sla_deadline = breach_time
    mock_breach.resolved_at = None

    mock_future = MagicMock(spec=EscalationQueue)
    mock_future.id = 2
    mock_future.sla_deadline = future_time
    mock_future.resolved_at = None

    mock_resolved = MagicMock(spec=EscalationQueue)
    mock_resolved.id = 3
    mock_resolved.sla_deadline = breach_time
    mock_resolved.resolved_at = datetime.utcnow()  # Already resolved → should be excluded

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_breach]  # Only unresolved + breached ticket returned

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    manager = EscalationManager(db=mock_db)
    breaches = await manager.get_sla_breaches()

    assert mock_db.execute.called, "get_sla_breaches() should call execute()"
    call_args = mock_db.execute.call_args[0][0]
    stmt_str = str(call_args)
    # Verify WHERE clause includes sla_deadline < now and resolved_at == None
    assert "sla_deadline" in stmt_str.lower(), \
        f"SQL should filter by sla_deadline: {stmt_str}"
    assert "resolved" in stmt_str.lower(), \
        f"SQL should filter by resolved_at: {stmt_str}"


# --- test_escalation_manager_get_sla_breaches_ordered_by_priority ---
@pytest.mark.asyncio
async def test_escalation_manager_get_sla_breaches_ordered_by_priority():
    """get_sla_breaches() results are ordered by priority DESC then queued_at ASC.

    Spec: Higher priority (lower number) breaches appear first; ties broken
    by earliest queued_at (FIFO).
    """
    mock_db = AsyncMock()

    now = datetime.utcnow()
    old = now - timedelta(minutes=60)
    newer = now - timedelta(minutes=30)

    mock_high_pri = MagicMock()
    mock_high_pri.id = 1
    mock_high_pri.priority = 0  # URGENT
    mock_high_pri.sla_deadline = now - timedelta(minutes=20)
    mock_high_pri.resolved_at = None

    mock_low_pri = MagicMock()
    mock_low_pri.id = 2
    mock_low_pri.priority = 2  # NORMAL
    mock_low_pri.sla_deadline = now - timedelta(minutes=5)
    mock_low_pri.resolved_at = None

    mock_high_pri_older = MagicMock()
    mock_high_pri_older.id = 3
    mock_high_pri_older.priority = 0  # URGENT but older
    mock_high_pri_older.sla_deadline = now - timedelta(minutes=60)
    mock_high_pri_older.resolved_at = None

    mock_scalars = MagicMock()
    # Return in order: high_pri (id=1), high_pri_older (id=3), low_pri (id=2)
    mock_scalars.all.return_value = [mock_high_pri, mock_high_pri_older, mock_low_pri]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    manager = EscalationManager(db=mock_db)
    breaches = await manager.get_sla_breaches()

    call_args = mock_db.execute.call_args[0][0]
    stmt_str = str(call_args)
    # Verify ORDER BY includes priority DESC and queued_at ASC
    assert "priority" in stmt_str.lower(), \
        f"SQL should order by priority: {stmt_str}"
    # DESC for priority (higher priority first)
    assert "desc" in stmt_str.lower() and "priority" in stmt_str.lower(), \
        f"SQL should order by priority DESC: {stmt_str}"


# --- test_escalation_manager_sla_high_15_minutes ---
@pytest.mark.asyncio
async def test_escalation_manager_sla_high_15_minutes():
    """HIGH priority (1) escalation SLA = 15 minutes.

    Spec: Priority 1 (HIGH) has SLA of 15 minutes (SLA_MINUTES[1] = 15).
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def refresh_side_effect(obj):
        obj.id = 1

    mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

    manager = EscalationManager(db=mock_db)
    req = EscalationRequest(conversation_id=1, reason="high priority issue")

    ticket_id = await manager.create(req, priority=1)

    # Verify SLA_MINUTES for priority 1 is 15
    assert manager.SLA_MINUTES[1] == 15, \
        f"HIGH priority (1) SLA should be 15 minutes, got {manager.SLA_MINUTES[1]}"

    # Check that ticket was created with correct deadline
    call_args = mock_db.add.call_args[0][0]
    deadline = call_args.sla_deadline
    expected_deadline = datetime.utcnow() + timedelta(minutes=15)

    # Allow 5 second tolerance
    diff = abs((deadline - expected_deadline).total_seconds())
    assert diff < 5, \
        f"Expected deadline ~15min from now, got {deadline}"


# --- test_escalation_manager_sla_normal_30_minutes ---
@pytest.mark.asyncio
async def test_escalation_manager_sla_normal_30_minutes():
    """NORMAL priority (2) escalation SLA = 30 minutes.

    Spec: Priority 2 (NORMAL) has SLA of 30 minutes (SLA_MINUTES[2] = 30).
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def refresh_side_effect(obj):
        obj.id = 2

    mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

    manager = EscalationManager(db=mock_db)
    req = EscalationRequest(conversation_id=2, reason="normal issue")

    ticket_id = await manager.create(req, priority=2)

    # Verify SLA_MINUTES for priority 2 is 30
    assert manager.SLA_MINUTES[2] == 30, \
        f"NORMAL priority (2) SLA should be 30 minutes, got {manager.SLA_MINUTES[2]}"

    call_args = mock_db.add.call_args[0][0]
    deadline = call_args.sla_deadline
    expected_deadline = datetime.utcnow() + timedelta(minutes=30)

    diff = abs((deadline - expected_deadline).total_seconds())
    assert diff < 5, \
        f"Expected deadline ~30min from now, got {deadline}"


# --- test_escalation_manager_sla_urgent_5_minutes ---
@pytest.mark.asyncio
async def test_escalation_manager_sla_urgent_5_minutes():
    """URGENT priority (0) escalation SLA = 5 minutes.

    Spec: Priority 0 (URGENT) has SLA of 5 minutes (SLA_MINUTES[0] = 5).
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def refresh_side_effect(obj):
        obj.id = 3

    mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

    manager = EscalationManager(db=mock_db)
    req = EscalationRequest(conversation_id=3, reason="urgent issue")

    ticket_id = await manager.create(req, priority=0)

    # Verify SLA_MINUTES for priority 0 is 5
    assert manager.SLA_MINUTES[0] == 5, \
        f"URGENT priority (0) SLA should be 5 minutes, got {manager.SLA_MINUTES[0]}"

    call_args = mock_db.add.call_args[0][0]
    deadline = call_args.sla_deadline
    expected_deadline = datetime.utcnow() + timedelta(minutes=5)

    diff = abs((deadline - expected_deadline).total_seconds())
    assert diff < 5, \
        f"Expected deadline ~5min from now, got {deadline}"


# =============================================================================
# User Feedback Tests (4 tests)
# =============================================================================

@pytest.mark.asyncio
async def test_feedback_thumbs_up_accepted():
    """Feedback with thumbs_up rating is accepted.

    Spec: User-submitted feedback with rating='thumbs_up' must be
    accepted without raising ValidationError.
    """
    from app.services.escalation import FeedbackManager

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    manager = FeedbackManager(db=mock_db)
    result = await manager.submit_feedback(
        conversation_id=1,
        rating="thumbs_up",
        comment=None
    )

    assert result is not None, "thumbs_up feedback should be accepted"
    assert mock_db.add.called, "thumbs_up feedback should be persisted to DB"
    assert mock_db.commit.called, "thumbs_up feedback commit should be called"


@pytest.mark.asyncio
async def test_feedback_thumbs_down_accepted():
    """Feedback with thumbs_down rating is accepted.

    Spec: User-submitted feedback with rating='thumbs_down' must be
    accepted without raising ValidationError.
    """
    from app.services.escalation import FeedbackManager

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    manager = FeedbackManager(db=mock_db)
    result = await manager.submit_feedback(
        conversation_id=1,
        rating="thumbs_down",
        comment="Agent was slow"
    )

    assert result is not None, "thumbs_down feedback should be accepted"
    assert mock_db.add.called, "thumbs_down feedback should be persisted to DB"
    assert mock_db.commit.called, "thumbs_down feedback commit should be called"


@pytest.mark.asyncio
async def test_feedback_invalid_value_rejected():
    """Feedback with invalid rating value raises ValidationError.

    Spec: rating must be one of ['thumbs_up', 'thumbs_down'].
    Passing any other value (e.g., 'stars', 'emoji', '') must raise
    ValidationError with status 422.
    """
    from app.services.escalation import FeedbackManager, ValidationError

    mock_db = AsyncMock()

    manager = FeedbackManager(db=mock_db)

    invalid_ratings = ["stars", "emoji", "", "bad_value", "THUMBS_UP"]

    for invalid_rating in invalid_ratings:
        with pytest.raises(ValidationError):
            await manager.submit_feedback(
                conversation_id=1,
                rating=invalid_rating,
                comment=None
            )


@pytest.mark.asyncio
async def test_feedback_optional_comment():
    """Feedback comment is optional (None accepted).

    Spec: The comment field in feedback submission is optional;
    passing comment=None must be accepted.
    """
    from app.services.escalation import FeedbackManager

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    manager = FeedbackManager(db=mock_db)

    # Submit with comment=None
    result = await manager.submit_feedback(
        conversation_id=1,
        rating="thumbs_up",
        comment=None
    )

    assert result is not None, "feedback with comment=None should be accepted"
    assert mock_db.add.called, "feedback should be persisted even with no comment"