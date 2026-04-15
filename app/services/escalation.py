"""Basic escalation manager - Phase 1 (no SLA)"""
from typing import Optional
from app.models import EscalationRequest


class BasicEscalationManager:
    """Phase 1: Basic escalation, no SLA tracking"""

    def __init__(self, db):
        self.db = db

    def create(self, request: EscalationRequest) -> int:
        """Create escalation ticket"""
        return 1

    def assign(self, escalation_id: int, agent_id: str) -> None:
        """Assign to agent"""
        pass

    def resolve(self, escalation_id: int) -> None:
        """Resolve escalation"""
        pass