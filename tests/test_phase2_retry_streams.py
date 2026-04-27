"""Phase 2 Tests: Retry + Redis Streams (Issues #23, #24, #31, #32)"""
import pytest
import asyncio
import time
import random
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from redis.exceptions import ResponseError

from app.utils.retry import RetryStrategy
from app.services.worker import AsyncMessageProcessor


# ==============================================================================
# Redis Streams Async Processing Tests (#23, #31)
# ==============================================================================

@pytest.mark.asyncio
async def test_async_message_processor_ensure_group_creates_group():
    """_ensure_group() creates consumer group on first call"""
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()

    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    await processor._ensure_group()

    mock_redis.xgroup_create.assert_called_once_with(
        "omnibot:messages",
        "test_group",
        id="0",
        mkstream=True,
    )


@pytest.mark.asyncio
async def test_async_message_processor_ensure_group_ignores_busygroup():
    """group already exists → BUSYGROUP error ignored"""
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock(
        side_effect=ResponseError("BUSYGROUP Consumer Group name already exists")
    )

    processor = AsyncMessageProcessor(mock_redis, group="test_group")

    # Should not raise, BUSYGROUP is silently ignored
    await processor._ensure_group()

    mock_redis.xgroup_create.assert_called_once()
    assert mock_redis.aclose.call_count == 0  # Connection not closed on BUSYGROUP


@pytest.mark.asyncio
async def test_async_message_processor_consume_returns_streams():
    """consume() returns Redis stream data"""
    mock_redis = AsyncMock()
    expected_streams = [["omnibot:messages", [["msg_id_1", {"key": "value"}]]]]
    mock_redis.xreadgroup = AsyncMock(return_value=expected_streams)

    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    result = await processor.consume("consumer_1", count=5)

    assert result == expected_streams
    mock_redis.xreadgroup.assert_called_once_with(
        "test_group",
        "consumer_1",
        {"omnibot:messages": ">"},
        count=5,
        block=5000,
    )


@pytest.mark.asyncio
async def test_async_message_processor_ack_marks_processed():
    """ack() marks message as processed"""
    mock_redis = AsyncMock()
    mock_redis.xack = AsyncMock()

    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    await processor.ack("omnibot:messages", "1234567890-0")

    mock_redis.xack.assert_called_once_with(
        "omnibot:messages",
        "test_group",
        "1234567890-0",
    )


@pytest.mark.asyncio
async def test_async_message_processor_classmethod_factory_creates_instance():
    """create() classmethod works"""
    mock_redis_instance = AsyncMock()
    mock_redis_instance.xgroup_create = AsyncMock()

    with patch("app.services.worker.aioredis.from_url", return_value=mock_redis_instance):
        processor = await AsyncMessageProcessor.create("redis://localhost", group="factory_test")

        assert isinstance(processor, AsyncMessageProcessor)
        assert processor.group == "factory_test"
        assert processor.redis is mock_redis_instance
        mock_redis_instance.xgroup_create.assert_called_once()


@pytest.mark.asyncio
async def test_async_message_processor_consume_with_block():
    """block=5000 passes correct timeout to Redis"""
    mock_redis = AsyncMock()
    mock_redis.xreadgroup = AsyncMock(return_value=[])

    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    await processor.consume("consumer_1", count=10, block_ms=5000)

    # Verify block=5000 is passed to xreadgroup (5 second timeout)
    mock_redis.xreadgroup.assert_called_once_with(
        "test_group",
        "consumer_1",
        {"omnibot:messages": ">"},
        count=10,
        block=5000,
    )


@pytest.mark.asyncio
async def test_async_message_processor_xreadgroup_reads_from_stream():
    """uses xreadgroup not xread"""
    mock_redis = AsyncMock()
    mock_redis.xreadgroup = AsyncMock(return_value=[])
    mock_redis.xread = AsyncMock()  # Should NOT be called

    processor = AsyncMessageProcessor(mock_redis, group="test_group")
    await processor.consume("consumer_1")

    # xreadgroup must be called, xread must NOT be called
    mock_redis.xreadgroup.assert_called_once()
    mock_redis.xread.assert_not_called()


# ==============================================================================
# Exponential Backoff Retry Tests (#24, #32)
# ==============================================================================

@pytest.mark.asyncio
async def test_retry_exponential_backoff_doubles():
    """2nd retry delay ≈ base_delay * 2"""
    base_delay = 0.1
    strategy = RetryStrategy(max_retries=3, base_delay=base_delay, jitter=False)

    sleep_delays = []

    async def tracking_sleep(delay):
        sleep_delays.append(delay)
        # Don't actually sleep - just record

    # Create a function that fails twice then succeeds
    call_count = 0

    async def mock_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("fail")
        return "done"

    with patch("app.utils.retry.asyncio.sleep", side_effect=tracking_sleep):
        result = await strategy.execute(mock_func)

    assert result == "done"
    # First delay: base_delay * 2^0 = 0.1
    # Second delay: base_delay * 2^1 = 0.2
    assert sleep_delays[0] == pytest.approx(0.1, abs=0.01)
    assert sleep_delays[1] == pytest.approx(0.2, abs=0.01)


@pytest.mark.asyncio
async def test_retry_exponential_backoff_capped_at_max_delay():
    """max delay never exceeds max_delay"""
    strategy = RetryStrategy(
        max_retries=5,
        base_delay=10.0,
        max_delay=15.0,
        jitter=False
    )

    sleep_delays = []

    async def tracking_sleep(delay):
        sleep_delays.append(delay)

    async def failing_func():
        raise Exception("always fails")

    with patch("asyncio.sleep", side_effect=tracking_sleep):
        with pytest.raises(Exception):
            await strategy.execute(failing_func)

    # All delays should be capped at max_delay (15.0)
    for delay in sleep_delays:
        assert delay <= 15.0, f"Delay {delay} exceeds max_delay 15.0"


@pytest.mark.asyncio
async def test_retry_jitter_randomizes_delay():
    """jitter enabled → delay has randomness"""
    strategy = RetryStrategy(max_retries=10, base_delay=1.0, jitter=True)

    sleep_delays = []

    async def tracking_sleep(delay):
        sleep_delays.append(delay)

    async def failing_func():
        raise Exception("fail")

    # Run multiple times to detect randomness
    all_delays = []
    for _ in range(5):
        sleep_delays.clear()
        with patch("asyncio.sleep", side_effect=tracking_sleep):
            with pytest.raises(Exception):
                await strategy.execute(failing_func)
        all_delays.extend(sleep_delays)

    # With jitter enabled, delays should vary (not all identical)
    unique_delays = set(round(d, 4) for d in all_delays)
    assert len(unique_delays) > 1, "Jitter should produce varying delays"


@pytest.mark.asyncio
async def test_retry_max_retries_respected():
    """exceeding max_retries → raises exception"""
    strategy = RetryStrategy(max_retries=2, base_delay=0.01, jitter=False)

    call_count = 0

    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise Exception("always fail")

    with pytest.raises(Exception, match="always fail"):
        await strategy.execute(always_fails)

    # max_retries=2 means: 1 initial + 2 retries = 3 total calls
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_succeeds_on_first_attempt_no_delay():
    """first success → no sleep"""
    strategy = RetryStrategy(max_retries=3, base_delay=1.0, jitter=True)

    sleep_called = False

    async def tracking_sleep(delay):
        nonlocal sleep_called
        sleep_called = True

    async def succeed_on_first():
        return "success"

    with patch("asyncio.sleep", side_effect=tracking_sleep):
        result = await strategy.execute(succeed_on_first)

    assert result == "success"
    assert sleep_called is False, "No sleep should occur on first attempt success"


@pytest.mark.asyncio
async def test_retry_returns_result_on_success():
    """success returns func result"""
    strategy = RetryStrategy(max_retries=3, base_delay=0.01)

    expected_result = {"status": "ok", "data": [1, 2, 3]}

    async def mock_func():
        return expected_result

    result = await strategy.execute(mock_func)
    assert result == expected_result


@pytest.mark.asyncio
async def test_retry_respects_max_delay():
    """delay capped at max_delay"""
    strategy = RetryStrategy(max_retries=10, base_delay=100.0, max_delay=30.0, jitter=False)

    sleep_delays = []

    async def tracking_sleep(delay):
        sleep_delays.append(delay)

    async def failing_func():
        raise Exception("fail")

    with patch("asyncio.sleep", side_effect=tracking_sleep):
        with pytest.raises(Exception):
            await strategy.execute(failing_func)

    # All delays should be capped at 30.0
    for delay in sleep_delays:
        assert delay <= 30.0, f"Delay {delay} exceeds max_delay 30.0"


@pytest.mark.asyncio
async def test_retry_jitter_half_to_full_range():
    """jitter delay in [0.5*delay, 1.5*delay] range"""
    strategy = RetryStrategy(max_retries=1, base_delay=1.0, jitter=True)

    sleep_delays = []
    base_expected = 1.0

    async def tracking_sleep(delay):
        sleep_delays.append(delay)

    async def failing_func():
        raise Exception("fail")

    with patch("asyncio.sleep", side_effect=tracking_sleep):
        with pytest.raises(Exception):
            await strategy.execute(failing_func)

    assert len(sleep_delays) == 1
    actual_delay = sleep_delays[0]

    # With jitter (0.5 + random * 1.0), range is [0.5*base, 1.5*base]
    assert 0.5 * base_expected <= actual_delay <= 1.5 * base_expected, \
        f"Delay {actual_delay} not in expected range [0.5, 1.5]"
