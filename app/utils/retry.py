"""Exponential Backoff Retry Strategy - Phase 3"""
import asyncio
import logging
import secrets
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")
logger = logging.getLogger("omnibot.retry")


class RetryStrategy:
    """Exponential backoff with jitter (Phase 3)"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    async def execute(self, func: Callable[..., Coroutine[Any, Any, T]], *args: Any, **kwargs: Any) -> T:
        """Execute a coroutine with retry logic"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self.max_retries:
                    logger.error(
                        f"Max retries ({self.max_retries}) reached. Operation failed: {e}")
                    raise

                # Calculate delay: base * 2^attempt
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)

                # Apply jitter (0.5 to 1.5 of calculated delay)
                if self.jitter:
                    delay *= 0.5 + secrets.SystemRandom().random()

                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception
        raise Exception("Retry failed without specific exception")
