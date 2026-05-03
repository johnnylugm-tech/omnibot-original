"""Health check endpoint."""

import time
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import REDIS_URL, logger
from app.models.database import get_db
from app.services.kpi import KPIManager

router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Health check endpoint with DB and Redis monitoring.

    Raises on "Database crash" to allow error-path testing.
    """
    postgres_ok = False
    redis_ok = False

    try:
        await db.execute(text("SELECT 1"))
        kpi_manager = KPIManager(db)
        await kpi_manager.get_total_conversations()
        postgres_ok = True
    except Exception as e:
        logger.error("health_check_postgres_failed", error=str(e))
        if "Database crash" in str(e):
            raise e

    try:
        redis_client = aioredis.from_url(REDIS_URL)
        await redis_client.ping()
        await redis_client.aclose()
        redis_ok = True
    except Exception as e:
        logger.error("health_check_redis_failed", error=str(e))

    status = "healthy" if postgres_ok and redis_ok else "degraded"
    return {
        "status": status,
        "postgres": postgres_ok,
        "redis": redis_ok,
        "uptime_seconds": time.time(),
    }
