"""Redis Streams Async Worker - Phase 3"""
import redis.asyncio as aioredis
from redis.exceptions import ResponseError
from typing import Optional, List, Any, Sequence


class AsyncMessageProcessor:
    """
    Redis Streams Consumer Group implementation for async message handling (Phase 3).
    Used for offloading non-critical tasks like long-running generation or analytics.
    """

    def __init__(self, redis_client: aioredis.Redis, group: str = "omnibot"):
        self.redis = redis_client
        self.group = group

    @classmethod
    async def create(cls, redis_url: str, group: str = "omnibot") -> "AsyncMessageProcessor":
        """Factory method to create processor and ensure consumer group exists"""
        redis_client = aioredis.from_url(redis_url)
        instance = cls(redis_client, group)
        await instance._ensure_group()
        return instance

    async def _ensure_group(self) -> None:
        """Create consumer group if not already present"""
        try:
            await self.redis.xgroup_create(
                "omnibot:messages",
                self.group,
                id="0",
                mkstream=True,
            )
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def produce(self, stream_name: str, payload: dict) -> str:
        """Add a message to the stream.

        Args:
            stream_name: Redis stream key (e.g. "omnibot:messages").
            payload: Dictionary of message fields. Required: ``conversation_id`` (int).
                    Other standard fields: ``role`` (str), ``content`` (str),
                    ``timestamp`` (str, ISO format).

        Returns:
            The Redis message ID of the inserted entry.

        Raises:
            redis.exceptions.ResponseError: If the stream does not exist
                and ``mkstream`` is not enabled on the consumer group.
        """
        return await self.redis.xadd(stream_name, payload)

    async def consume(
        self,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 5000,
        id_mode: str = ">"
    ) -> List[Any]:
        """Consume messages from the group. id_mode='>' for new, id_mode='0' for PEL."""
        streams = await self.redis.xreadgroup(
            self.group,
            consumer_name,
            {"omnibot:messages": id_mode},
            count=count,
            block=block_ms,
        )
        return streams

    async def ack(self, stream_name: str, message_id: str) -> None:
        """Acknowledge message processing"""
        await self.redis.xack(stream_name, self.group, message_id)

    async def get_pending(self, stream_name: str, count: int = 10) -> List[Any]:
        """Get pending messages from the group's PEL with ID deduplication"""
        # xpending_range format: [message_id, consumer, idle_time, deliveries]
        raw_pending = await self.redis.xpending_range(
            stream_name, self.group, "-", "+", count
        )
        
        if not raw_pending:
            return []

        # Dedup based on message_id (entry[0]) while preserving order
        seen_ids = set()
        unique_pending = []
        for entry in raw_pending:
            msg_id = entry[0]
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                unique_pending.append(entry)
        return unique_pending

    async def claim_stale_message(
        self,
        stream_name: str,
        consumer_name: str,
        min_idle_time_ms: int,
        message_ids: Sequence[str]
    ) -> List[Any]:
        """Claim stale messages from another consumer with ID deduplication"""
        # Deduplicate using dict.fromkeys for order preservation
        unique_ids = list(dict.fromkeys(message_ids))
        return await self.redis.xclaim(
            stream_name,
            self.group,
            consumer_name,
            min_idle_time_ms,
            unique_ids  # type: ignore[arg-type]
        )

    # Alias for backward compatibility
    claim = claim_stale_message

    async def close(self) -> None:
        """Close redis connection"""
        await self.redis.aclose()
