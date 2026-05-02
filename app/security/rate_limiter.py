"""Rate limiter - Token Bucket with Redis support"""
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("omnibot.rate_limiter")


@dataclass
class TokenBucket:
    """Token bucket rate limiter (In-memory fallback)"""
    capacity: int
    refill_rate: float
    _tokens: float = 0.0
    _last_refill: float = 0.0

    def __post_init__(self) -> None:
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens +
                           elapsed * self.refill_rate)
        self._last_refill = now
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False


class RateLimiter:
    """Per-platform per-user rate limiter with Redis backend and in-memory fallback"""

    def __init__(self, redis_url: Optional[str] = None, default_rps: int = 10, burst_factor: float = 1.0):
        self._default_rps = default_rps
        self._burst_factor = burst_factor
        self._redis_url = redis_url or os.getenv("REDIS_URL")
        self._redis = None
        self._local_buckets: Dict[str, TokenBucket] = {}

        # Lua script with Redis-side timestamp for accuracy
        self._lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local requested = tonumber(ARGV[3])
        
        -- Get Redis server time
        local time = redis.call('TIME')
        local now = tonumber(time[1]) + tonumber(time[2]) / 1000000

        local bucket = redis.call("HMGET", key, "tokens", "last_refill")
        local tokens = tonumber(bucket[1]) or capacity
        local last_refill = tonumber(bucket[2]) or now

        local elapsed = math.max(0, now - last_refill)
        tokens = math.min(capacity, tokens + elapsed * refill_rate)

        if tokens >= requested then
            tokens = tokens - requested
            redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
            redis.call("EXPIRE", key, 3600)
            return 1
        else
            redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
            return 0
        end
        """

    async def _get_redis(self) -> Any:
        if self._redis is None and self._redis_url:
            import redis.asyncio as aioredis
            try:
                self._redis = aioredis.from_url(
                    self._redis_url, decode_responses=True)
                if self._redis:
                    await self._redis.ping()
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._redis = None
        return self._redis

    async def check(self, platform: str, user_id: str) -> bool:
        """Check rate limit for a user. Returns True if allowed."""
        key = f"ratelimit:{platform}:{user_id}"
        redis_conn = await self._get_redis()

        # Capacity calculation: Allow burst based on factor
        capacity = max(1, int(self._default_rps * self._burst_factor))

        if redis_conn:
            try:
                # result = 1 if allowed, 0 if blocked
                result = await redis_conn.eval(
                    self._lua_script, 1, key,
                    capacity, float(self._default_rps), 1
                )
                return bool(result)
            except Exception as e:
                logger.warning(
                    f"Redis rate limit check failed, falling back to in-memory: {e}")

        # Fallback to in-memory
        local_key = f"{platform}:{user_id}"
        if local_key not in self._local_buckets:
            self._local_buckets[local_key] = TokenBucket(
                capacity, float(self._default_rps))

        self._local_buckets[local_key].capacity = capacity
        self._local_buckets[local_key].refill_rate = float(self._default_rps)

        return self._local_buckets[local_key].consume()
