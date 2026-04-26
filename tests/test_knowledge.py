import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.knowledge import HybridKnowledgeV7

@pytest.mark.asyncio
async def test_hybrid_knowledge_layer():
    # Mock DB
    mock_db = AsyncMock()
    # Mock execute result to be empty for both rule match and RAG
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_execute_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_execute_result
    
    layer = HybridKnowledgeV7(db=mock_db)

    # query method
    res = await layer.query("test")
    assert res is not None
    assert "正在為您轉接人工客服" in res.content
    assert res.source == "escalate"
