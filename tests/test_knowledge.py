import os

os.environ["SIMULATE_LLM"] = "false"
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import KnowledgeResult
from app.services.knowledge import HybridKnowledgeV7


@pytest.mark.asyncio
async def test_hybrid_knowledge_layer_escalate():
    mock_db = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_execute_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_execute_result

    layer = HybridKnowledgeV7(db=mock_db)
    layer.llm = None  # Disable LLM

    # Short query or disabled LLM triggers escalation
    res = await layer.query("t")
    assert res is not None
    assert res.source == "escalate"


@pytest.mark.asyncio
async def test_grounding_check():
    mock_db = AsyncMock()
    layer = HybridKnowledgeV7(db=mock_db)

    source = KnowledgeResult(
        id=1, content="課程資訊包含 Python 與 AI 實戰", confidence=0.9, source="rule"
    )
    response = KnowledgeResult(
        id=0, content="這門課程提供 Python 實戰教學", confidence=0.8, source="llm"
    )

    res = layer.grounding_checker.check(response, [source])
    assert res["grounded"] is True


@pytest.mark.asyncio
async def test_hybrid_knowledge_with_llm_and_grounding():
    mock_db = AsyncMock()
    # Mock results to fall through to Layer 3 (LLM) but PROVIDE one source for grounding
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    # RAG search returns one result
    mock_execute_result.fetchall.return_value = [(1, "source context", 0.5)]
    mock_db.execute.return_value = mock_execute_result

    layer = HybridKnowledgeV7(db=mock_db, llm_client=True)

    # Case A: Grounding succeeds
    with patch.object(
        layer.grounding_checker, "check", return_value={"grounded": True, "score": 0.9}
    ):
        res = await layer.query("課程")
        assert res.source == "llm"

    # Case B: Grounding fails
    with patch.object(
        layer.grounding_checker, "check", return_value={"grounded": False, "score": 0.4}
    ):
        res = await layer.query("課程")
        assert res.source == "escalate"
