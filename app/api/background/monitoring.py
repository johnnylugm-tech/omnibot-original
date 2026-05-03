"""Background monitoring task for automated SLA and error monitoring."""

import asyncio

from app.api.deps import alert_manager, logger
from app.models.database import AsyncSessionLocal
from app.services.escalation import EscalationManager


async def automated_monitoring_loop() -> None:
    """
    Background task that periodically checks SLA breaches and system health.

    Runs every 60 seconds while the application is alive.
    """
    while True:
        try:
            async with AsyncSessionLocal() as db:
                esc_manager = EscalationManager(db)
                breaches = await esc_manager.get_sla_breaches()
                if breaches:
                    await alert_manager.check_sla_breach(len(breaches))

            # No artificial delay — let the loop naturally re-await on next tick
        except asyncio.CancelledError:
            logger.info("monitoring_loop_cancelled")
            raise
        except Exception as e:
            logger.error("monitoring_loop_error", error=str(e))

        await asyncio.sleep(60)
