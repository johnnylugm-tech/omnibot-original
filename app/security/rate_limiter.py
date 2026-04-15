"""Rate limiter - Token Bucket"""
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    """Token bucket rate limiter"""
    capacity: int
    refill_rate: float
    _tokens: float = 0.0
    _last_refill: float = 0.0

    def __post_init__(self):
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False


class RateLimiter:
    """Per-platform per-user rate limiter"""
    def __init__(self, default_rps: int = 100):
        self._buckets = {}
        self._default_rps = default_rps

    def check(self, platform: str, user_id: str) -> bool:
        key = f"{platform}:{user_id}"
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(self._default_rps, float(self._default_rps))
        return self._buckets[key].consume()
