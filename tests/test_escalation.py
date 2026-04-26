import pytest
from unittest.mock import AsyncMock, MagicMock
from app.models import EscalationRequest
from app.services.escalation import EscalationManager


@pytest.mark.asyncio
async def test_escalation_manager():
    mock_db = AsyncMock()
    # Mock ticket creation result
    mock_ticket = MagicMock()
    mock_ticket.id = 1
    mock_db.add = MagicMock()
    
    manager = EscalationManager(db=mock_db)
    req = EscalationRequest(conversation_id=1, reason="test")
    
    # Mock commit/refresh
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    
    # Set the ID manually on the mock since refresh won't do it
    async def side_effect(obj):
        obj.id = 1
    mock_db.refresh.side_effect = side_effect

    res_id = await manager.create(req)
    assert res_id == 1
    await manager.assign(1, "agent1")
    await manager.resolve(1)
