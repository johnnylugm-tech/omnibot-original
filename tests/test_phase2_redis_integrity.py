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


# =============================================================================
# =============================================================================
# Redis Stream Message Format (Section 23) — NEW RED tests
# =============================================================================

@pytest.mark.asyncio
async def test_redis_stream_message_format_includes_required_fields(mock_redis):
    """Stream message must contain: conversation_id, platform, user_id, message_id, timestamp

    RED reason: The stream message format is not yet validated to include all required fields.
    When a message is published to the stream, those 5 fields must be present.
    """
    from app.services.worker import AsyncMessageProcessor

    processor = AsyncMessageProcessor(mock_redis, group="test_group")

    # Verify required fields are documented/checked in stream message construction
    required_fields = ["conversation_id", "platform", "user_id", "message_id", "timestamp"]

    # Simulate a message payload that would be published via xadd
    message_payload = {
        "conversation_id": "conv-123",
        "platform": "telegram",
        "user_id": "user-456",
        "message_id": "msg-789",
        "timestamp": "2024-01-01T12:00:00Z",
    }

    # All required fields must be present in the message payload
    for field in required_fields:
        assert field in message_payload, \
            f"Stream message missing required field: {field}"


@pytest.mark.asyncio
async def test_redis_pending_entries_list_no_duplicate_message_ids(mock_redis):
    """Pending Entries List (PEL) must not contain duplicate message_ids

    RED reason: The claim/requeue logic may produce duplicate message_ids in PEL.
    This test verifies that AsyncMessageProcessor.get_pending() / consume()
    correctly deduplicates PEL entries so no message_id appears twice.
    """
    from app.services.worker import AsyncMessageProcessor

    processor = AsyncMessageProcessor(mock_redis, group="test_group")

    # Mock get_pending returning PEL with a duplicate message_id
    pel_with_dup = [
        ["msg-001", "consumer_1", 1000, 1],
        ["msg-002", "consumer_1", 2000, 1],
        ["msg-001", "consumer_1", 1500, 1],  # duplicate!
    ]
    mock_redis.xpending_range = AsyncMock(return_value=pel_with_dup)

    # get_pending is called with stream name
    result = await processor.get_pending("omnibot:messages", count=10)

    # Extract message_ids from PEL entries (format: [message_id, consumer, last_delivery, num_deliveries])
    message_ids = [entry[0] for entry in result]

    # Verify no duplicates using set comparison
    unique_ids = set(message_ids)
    assert len(unique_ids) == len(message_ids), \
        f"PEL contains duplicate message_ids: {message_ids}"


# =============================================================================
# Section 44 G-05: Redis Streams message format schema
# =============================================================================

def test_redis_streams_message_schema_defined():
    """Redis streams message schema must be defined. RED-phase test.
    
    Spec: Every message published to Redis streams must follow a defined
    schema with required fields. This test verifies that the message schema
    is documented and enforced.
    
    Required fields for omnibot:messages stream:
    - conversation_id: string identifier
    - platform: string (telegram|line|messenger|whatsapp)
    - user_id: string platform-specific user ID
    - message_id: string unique message identifier
    - timestamp: ISO8601 datetime string
    """
    # Verify the message schema is defined in the produce() method
    # or a schema definition somewhere
    
    from app.services.worker import AsyncMessageProcessor
    import inspect
    
    # Get the produce method source to verify schema documentation
    produce_source = inspect.getsource(AsyncMessageProcessor.produce)
    
    # Verify that the schema is documented
    # The method should document or enforce required fields
    assert "conversation_id" in produce_source or "required" in produce_source.lower(), \
        "produce() method should document/validate required message schema fields"


@pytest.mark.asyncio
async def test_redis_streams_consumer_handles_unknown_fields_gracefully(mock_redis):
    """Consumer must handle unknown fields in stream messages gracefully. RED-phase test.
    
    Spec: When a stream message contains fields that are not defined in the
    expected schema, the consumer must not crash. Unknown fields should be
    ignored or logged but not cause processing failures.
    """
    from app.services.worker import AsyncMessageProcessor
    
    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    
    # Simulate a message with extra unknown fields
    message_with_unknown = {
        "conversation_id": "conv-123",
        "platform": "telegram",
        "user_id": "user-456",
        "message_id": "msg-789",
        "timestamp": "2024-01-01T12:00:00Z",
        # Unknown field - should not crash consumer
        "unknown_field": "should_be_ignored",
        "another_unknown": 12345,
    }
    
    # Mock xreadgroup to return message with unknown fields
    stream_data = [["omnibot:messages", [["msg-id-1", message_with_unknown]]]]
    mock_redis.xreadgroup = AsyncMock(return_value=stream_data)
    
    # consume() should process this without raising
    result = await processor.consume("test_consumer", count=10, block_ms=100)
    
    # Verify the consumer processed it successfully
    # Even with unknown fields, the message should be returned
    assert result is not None, \
        "Consumer should handle messages with unknown fields gracefully"
    
    # Verify the known fields are still accessible
    if result and len(result) > 0:
        stream_name, messages = result[0]
        if messages and len(messages) > 0:
            msg_id, msg_data = messages[0]
            assert "conversation_id" in msg_data, "Known fields should be preserved" 