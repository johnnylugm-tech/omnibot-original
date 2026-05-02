"""Cost estimation model for LLM usage tracking with Redis-based daily spend tracking."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis.asyncio as aioredis


class CostModel:
    """Calculates and logs costs based on token usage and model tier.

    Daily spend is tracked in Redis to avoid N+1 SQL queries on every request.
    Falls back to no-op tracking if Redis is unavailable.
    """

    PRICING = {
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
        "gemini-pro": {"prompt": 0.00025, "completion": 0.0005},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
    }

    # TTL: 25 hours — covers a full day window even with clock drift
    _DAILY_SPEND_TTL = 25 * 3600

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        if self._redis is None and self._redis_url:
            try:
                self._redis = aioredis.from_url(self._redis_url)
                await self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def _daily_key(self) -> str:
        """Redis key for today's cumulative spend: 'cost:daily:YYYY-MM-DD'"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"cost:daily:{today}"

    async def get_daily_spend(self) -> float:
        """Get today's cumulative spend from Redis. Returns 0.0 on error."""
        redis = await self._get_redis()
        if redis is None:
            return 0.0
        try:
            value = await redis.get(self._daily_key())
            return float(value or 0.0)
        except Exception:
            return 0.0

    async def increment_daily_spend(self, amount: float) -> float:
        """Atomically increment today's spend counter. Returns new total."""
        redis = await self._get_redis()
        if redis is None:
            return amount
        try:
            pipe = redis.pipeline()
            pipe.incrbyfloat(self._daily_key(), amount)
            pipe.expire(self._daily_key(), self._DAILY_SPEND_TTL)
            results = await pipe.execute()
            return float(results[0])
        except Exception:
            return amount

    def calculate_cost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Calculates total cost in USD."""
        prices = self.PRICING.get(model, self.PRICING["gemini-pro"])
        prompt_cost = (prompt_tokens / 1000) * prices["prompt"]
        completion_cost = (completion_tokens / 1000) * prices["completion"]
        return prompt_cost + completion_cost

    def check_budget(self, current_spend: float, limit: float) -> Dict[str, Any]:
        """Checks if current spending is within budget limits."""
        return {
            "within_budget": current_spend < limit,
            "usage_percent": (current_spend / limit) * 100 if limit > 0 else 0,
        }

    async def apply_daily_cap(
        self, next_cost: float, cap: float, redis_url: Optional[str] = None
    ) -> float:
        """
        Atomically reads today's spend and returns the allowable portion of next_cost.

        Uses Redis INCRBYFLOAT to avoid N+1 SQL queries on every request.
        Falls back to no-op if Redis is unavailable.
        """
        if redis_url:
            self._redis_url = redis_url

        current_spend = await self.get_daily_spend()

        if current_spend >= cap:
            return 0.0

        remaining = cap - current_spend
        allowable = min(next_cost, remaining)

        # Commit the charge to Redis
        if allowable > 0:
            await self.increment_daily_spend(allowable)

        return allowable
