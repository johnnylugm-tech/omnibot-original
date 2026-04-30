"""
RED Gaps Verification - Phase 2
Focus: Redis PEL dedup and SLA Threshold correctness.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.worker import AsyncMessageProcessor
from app.services.escalation import EscalationManager
from app.models import EscalationRequest
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_redis_pending_entries_list_no_duplicate_message_ids():
    """test_id_23_06: AsyncMessageProcessor.claim 必須對傳入的 message_ids 去重"""
    mock_redis = AsyncMock()
    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    
    # Duplicate IDs in request
    message_ids = ["msg-001", "msg-002", "msg-001"]
    
    await processor.claim(
        stream_name="test_stream",
        consumer_name="new_consumer",
        min_idle_time_ms=30000,
        message_ids=message_ids
    )
    
    # Verify xclaim was called with UNIQUE ids
    args, kwargs = mock_redis.xclaim.call_args
    sent_ids = args[4] # 5th positional arg is message_ids
    assert len(sent_ids) == 2, f"Expected 2 unique IDs, got {len(sent_ids)}"
    assert set(sent_ids) == {"msg-001", "msg-002"}

@pytest.mark.asyncio
async def test_sla_breach_detection_varies_by_priority():
    """test_id_21_07: SLA 閾值必須符合 p0=15min, p1=30min, p2=120min"""
    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    
    manager = EscalationManager(mock_db)
    
    # Test p0 (priority 0) -> 15 min
    req = EscalationRequest(conversation_id="c1", reason="test")
    await manager.create(req, priority=0)
    added_p0 = mock_db.add.call_args[0][0]
    expected_p0 = datetime.utcnow() + timedelta(minutes=15)
    assert abs((added_p0.sla_deadline - expected_p0).total_seconds()) < 5, "p0 SLA should be 15 min"
    
    # Test p1 (priority 1) -> 30 min
    await manager.create(req, priority=1)
    added_p1 = mock_db.add.call_args[0][0]
    expected_p1 = datetime.utcnow() + timedelta(minutes=30)
    assert abs((added_p1.sla_deadline - expected_p1).total_seconds()) < 5, "p1 SLA should be 30 min"
    
    # Test p2 (priority 2) -> 120 min
    await manager.create(req, priority=2)
    added_p2 = mock_db.add.call_args[0][0]
    expected_p2 = datetime.utcnow() + timedelta(minutes=120)
    assert abs((added_p2.sla_deadline - expected_p2).total_seconds()) < 5, "p2 SLA should be 120 min"
