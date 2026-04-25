from app.models import EscalationRequest
from app.services.escalation import BasicEscalationManager


def test_escalation_manager():
    manager = BasicEscalationManager(db=None)
    req = EscalationRequest(conversation_id=1, reason="test")
    assert manager.create(req) == 1
    assert manager.assign(1, "agent1") is None
    assert manager.resolve(1) is None
