import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.knowledge import HybridKnowledgeV7, KnowledgeResult

@pytest.mark.asyncio
async def test_hybrid_knowledge_layer_escalate():
    # Mock DB
    mock_db = AsyncMock()
    # Mock execute result to be empty
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_execute_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_execute_result
    
    layer = HybridKnowledgeV7(db=mock_db)

    # query method - should escalate if no matches
    res = await layer.query("test")
    assert res is not None
    assert "正在為您轉接人工客服" in res.content
    assert res.source == "escalate"

@pytest.mark.asyncio
async def test_grounding_check():
    mock_db = AsyncMock()
    layer = HybridKnowledgeV7(db=mock_db)
    
    # 1. Grounded response
    source = KnowledgeResult(id=1, content="課程資訊包含 Python 與 AI 實戰", confidence=0.9, source="rule")
    response = KnowledgeResult(id=0, content="這門課程提供 Python 實戰教學", confidence=0.8, source="llm")
    
    assert await layer._grounding_check(response, [source]) is True
    
    # 2. Hallucinated response (no overlap)
    hallucination = KnowledgeResult(id=0, content="今天的氣象預報是晴天", confidence=0.8, source="llm")
    assert await layer._grounding_check(hallucination, [source]) is False

@pytest.mark.asyncio
async def test_hybrid_knowledge_with_llm_and_grounding():
    mock_db = AsyncMock()
    # Mock results to fall through to Layer 3 (LLM)
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_execute_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_execute_result
    
    # Mock LLM generation
    layer = HybridKnowledgeV7(db=mock_db, llm_client=True)
    
    # Case A: Grounding succeeds (simulated LLM returns something that matches sources? 
    # Wait, our simulated LLM returns a fixed string. 
    # If sources are empty, grounding_check currently returns True.
    res = await layer.query("課程")
    assert res.source == "llm"
    
    # Case B: Grounding fails (we can mock _grounding_check)
    with patch.object(HybridKnowledgeV7, "_grounding_check", return_value=False):
        res = await layer.query("課程")
        assert res.source == "escalate"
