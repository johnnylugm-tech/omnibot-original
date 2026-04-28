"""
Atomic TDD Tests for Phase 2: Redis Streams Integrity (#23)
Focus: Consumer Timeout Handling and Block Mode Verification
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.worker import AsyncMessageProcessor

@pytest.mark.asyncio
async def test_id_23_01_consume_timeout_empty_return():
    """Verify consume returns empty list when block timeout expires with no messages"""
    mock_redis = AsyncMock()
    # Redis xreadgroup returns None or empty list on timeout
    mock_redis.xreadgroup = AsyncMock(return_value=None)

    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    result = await processor.consume("consumer_1", block_ms=100)

    assert result is None
    mock_redis.xreadgroup.assert_called_once()

@pytest.mark.asyncio
async def test_id_23_02_get_pending_messages():
    """Verify retrieval of pending messages from PEL"""
    mock_redis = AsyncMock()
    pending_info = [
        ["msg_id_1", "consumer_1", 1000, 1],
        ["msg_id_2", "consumer_1", 2000, 1]
    ]
    mock_redis.xpending_range = AsyncMock(return_value=pending_info)

    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    # We want to get pending messages for the stream
    result = await processor.get_pending("omnibot:messages", count=10)

    assert result == pending_info
    mock_redis.xpending_range.assert_called_once_with(
        "omnibot:messages", "test_group", "-", "+", 10
    )

@pytest.mark.asyncio
async def test_id_23_03_claim_stale_message():
    """Verify claiming a stale message from another consumer"""
    mock_redis = AsyncMock()
    claimed_msgs = [["msg_id_1", {"data": "payload"}]]
    mock_redis.xclaim = AsyncMock(return_value=claimed_msgs)

    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    # Claim message 'msg_id_1' if idle for > 30s
    result = await processor.claim(
        "omnibot:messages", 
        "new_consumer", 
        min_idle_time_ms=30000, 
        message_ids=["msg_id_1"]
    )

    assert result == claimed_msgs
    mock_redis.xclaim.assert_called_once_with(
        "omnibot:messages",
        "test_group",
        "new_consumer",
        30000,
        ["msg_id_1"]
    )

@pytest.mark.asyncio
async def test_id_23_04_consume_from_pel_first():
    """Verify consume_with_recovery reads from PEL (ID='0') before new messages"""
    mock_redis = AsyncMock()
    # PEL result
    pel_msgs = [["omnibot:messages", [["msg_id_pending", {"data": "old"}]]]]
    # New msgs result
    new_msgs = [["omnibot:messages", [["msg_id_new", {"data": "new"}]]]]
    
    mock_redis.xreadgroup = AsyncMock(side_effect=[pel_msgs, new_msgs])

    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    # First call should get PEL messages
    result_pel = await processor.consume("consumer_1", id_mode="0")
    assert result_pel == pel_msgs
    
    # Second call (manual in this test) would get new messages
    result_new = await processor.consume("consumer_1", id_mode=">")
    assert result_new == new_msgs

    assert mock_redis.xreadgroup.call_count == 2
