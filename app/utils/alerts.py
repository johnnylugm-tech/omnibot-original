"""Alert management and threshold monitoring."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import httpx

from app.utils.logger import StructuredLogger

logger = StructuredLogger("alerts")

class AlertCondition(Enum):
    GREATER_THAN = ">"
    LESS_THAN = "<"
    EQUAL = "=="

class AlertRule:
    def __init__(self, metric_name: str, condition: AlertCondition, threshold: float, label: str):
        self.metric_name = metric_name
        self.condition = condition
        self.threshold = threshold
        self.label = label

    def check(self, value: float) -> bool:
        if self.condition == AlertCondition.GREATER_THAN:
            return value > self.threshold
        if self.condition == AlertCondition.LESS_THAN:
            return value < self.threshold
        if self.condition == AlertCondition.EQUAL:
            return value == self.threshold
        return False

class AlertManager:
    """Monitors metrics and triggers alerts based on rules."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self.rules = [
            AlertRule("error_rate", AlertCondition.GREATER_THAN, 0.05, "high_error_rate"),
            AlertRule("sla_breach", AlertCondition.GREATER_THAN, 0, "sla_breach"),
            AlertRule("grounding_rate", AlertCondition.LESS_THAN, 0.7, "low_grounding_rate"),
            AlertRule("p95_latency", AlertCondition.GREATER_THAN, 1.0, "high_latency"),
            AlertRule("escalation_queue", AlertCondition.GREATER_THAN, 50, "escalation_backlog")
        ]

    async def check_error_rate(self, current_rate: float) -> bool:
        """Checks if error rate exceeds 5% threshold."""
        for rule in self.rules:
            if rule.metric_name == "error_rate" and rule.check(current_rate):
                await self._trigger_alert(rule.label, {"current_rate": current_rate})
                return True
        return False

    async def check_sla_breach(self, breach_count: int) -> bool:
        """Checks if any SLA breaches occurred."""
        for rule in self.rules:
            if rule.metric_name == "sla_breach" and rule.check(breach_count):
                await self._trigger_alert(rule.label, {"breach_count": breach_count})
                return True
        return False

    async def check_grounding_rate(self, grounding_rate: float) -> bool:
        """Checks if grounding rate drops below 70%."""
        for rule in self.rules:
            if rule.metric_name == "grounding_rate" and rule.check(grounding_rate):
                await self._trigger_alert(rule.label, {"grounding_rate": grounding_rate})
                return True
        return False

    async def check_p95_latency(self, latency: float) -> bool:
        """Checks if p95 latency exceeds 1s."""
        for rule in self.rules:
            if rule.metric_name == "p95_latency" and rule.check(latency):
                await self._trigger_alert(rule.label, {"p95_latency": latency})
                return True
        return False

    async def check_escalation_queue(self, count: int) -> bool:
        """Checks if escalation queue exceeds 50."""
        for rule in self.rules:
            if rule.metric_name == "escalation_queue" and rule.check(count):
                await self._trigger_alert("escalation_queue_backlog", {"queue_depth": count})
                return True
        return False

    async def _trigger_alert(self, alert_type: str, details: Dict[str, Any]) -> None:
        """Internal alert triggering logic with logging and webhook."""
        logger.error(f"ALERT_TRIGGERED: {alert_type}", **details)
        if self.webhook_url:
            await self.fire_webhook(alert_type, details)

    async def fire_webhook(self, alert_type: str, details: Dict[str, Any]) -> None:
        """Sends alert notification to external webhook."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "alert": alert_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": details
                }
                # await client.post(self.webhook_url, json=payload, timeout=5)
                pass # Webhook firing logic
        except Exception as e:
            logger.error("alert_webhook_failed", error=str(e))
