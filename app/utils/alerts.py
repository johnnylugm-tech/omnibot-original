"""Alerting system for monitoring system health and business KPIs."""
import os
import httpx
from typing import Optional, Dict, Any
from datetime import datetime

class AlertManager:
    """Manages alert conditions and fires webhooks for incidents."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("OMNIBOT_ALERT_WEBHOOK")
        self.active_alerts = set()

    async def check_error_rate(self, error_rate: float, threshold: float = 0.05) -> bool:
        """Check if error rate exceeds threshold and trigger alert."""
        if error_rate > threshold:
            await self._trigger_alert("high_error_rate", {"error_rate": error_rate, "threshold": threshold})
            return True
        elif "high_error_rate" in self.active_alerts:
            await self._resolve_alert("high_error_rate")
        return False

    async def check_sla_breach(self, breach_count: int) -> bool:
        """Trigger alert if any SLA breaches are detected."""
        if breach_count > 0:
            await self._trigger_alert("sla_breach", {"breach_count": breach_count})
            return True
        return False

    async def check_grounding_rate(self, grounding_rate: float, threshold: float = 0.7) -> bool:
        """Trigger alert if grounding rate falls below threshold."""
        if grounding_rate < threshold:
            await self._trigger_alert("low_grounding_rate", {"grounding_rate": grounding_rate, "threshold": threshold})
            return True
        return False

    async def _trigger_alert(self, alert_id: str, data: Dict[str, Any]):
        """Internal method to fire the webhook and track active alert."""
        if alert_id not in self.active_alerts:
            self.active_alerts.add(alert_id)
            await self.fire_webhook(f"ALERT: {alert_id}", data)

    async def _resolve_alert(self, alert_id: str):
        """Internal method to fire a resolution webhook."""
        if alert_id in self.active_alerts:
            self.active_alerts.remove(alert_id)
            await self.fire_webhook(f"RESOLVED: {alert_id}", {"resolved_at": datetime.utcnow().isoformat()})

    async def fire_webhook(self, message: str, payload: Dict[str, Any]):
        """Sends an alert message to the configured webhook URL."""
        if not self.webhook_url:
            return

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.webhook_url,
                    json={"message": message, "data": payload, "timestamp": datetime.utcnow().isoformat()},
                    timeout=5.0
                )
                response.raise_for_status()
            except Exception as e:
                # Log error but don't crash
                print(f"Failed to fire alert webhook: {e}")

class AlertCondition:
    """Represents a logic condition for an alert."""
    pass

class AlertRule:
    """Represents a combined rule and destination for alerts."""
    pass
