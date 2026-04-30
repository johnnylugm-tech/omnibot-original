"""
Phase 2 Hybrid Knowledge Layer — Rule Match Confidence Gate Tests (Section 17)

These tests verify the confidence threshold logic in HybridKnowledgeLayer:
- confidence > 0.9 → adopt rule result directly (no RRF fusion)
- confidence <= 0.9 → trigger RRF fusion

RED stage: these tests FAIL until the confidence gate is implemented.
"""
import os
os.environ['SIMULATE_LLM'] = 'false'
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Only SKIP the import if the module truly doesn't exist.
# We patch at the class level so the tests can still run with proper mocking.
try:
    import app.services.hybrid_knowledge as hybrid_knowledge
    HAS_HYBRID = True
except ImportError:
    HAS_HYBRID = False


@pytest.mark.skipif(not HAS_HYBRID, reason="app.services.hybrid_knowledge not yet implemented")
@pytest.mark.asyncio
async def test_hybrid_layer_rule_match_confidence_above_0_9():
    """Layer 1 (rule) confidence > 0.9 → adopt rule result directly, source='rule'

    RED reason: HybridKnowledgeLayer.query() must check Layer 1 confidence threshold.
    When confidence > 0.9, the method should short-circuit RRF and return the rule result.
    RAG must NOT be called when rule confidence is already high enough.
    """
    HybridKnowledgeLayer = hybrid_knowledge.HybridKnowledgeLayer
    KnowledgeResult = hybrid_knowledge.KnowledgeResult
    mock_db = AsyncMock()

    with patch.object(HybridKnowledgeLayer, "_rule_search", new_callable=AsyncMock) as mock_rule:
        # Layer 1 returns high-confidence rule match (0.95 > 0.9)
        mock_rule.return_value = [
            KnowledgeResult(id=1, content="high confidence rule doc", confidence=0.95, source="rule")
        ]

        with patch.object(HybridKnowledgeLayer, "_rag_search", new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = []

            layer = HybridKnowledgeLayer(db=mock_db)
            result = await layer.query("test query")

            assert result is not None
            assert result.source == "rule", \
                f"Expected source='rule' but got source='{result.source}'"
            assert result.confidence > 0.9
            # RAG should NOT have been called when rule confidence is high enough
            mock_rag.assert_not_called()


@pytest.mark.skipif(not HAS_HYBRID, reason="app.services.hybrid_knowledge not yet implemented")
@pytest.mark.asyncio
async def test_hybrid_layer_rule_match_confidence_below_0_9_triggers_rrf():
    """Layer 1 (rule) confidence <= 0.9 → trigger RRF fusion of rule + rag results

    RED reason: HybridKnowledgeLayer.query() must check Layer 1 confidence threshold.
    When confidence <= 0.9, RRF fusion should be triggered to improve ranking.
    Both rule and rag results should be considered.
    """
    HybridKnowledgeLayer = hybrid_knowledge.HybridKnowledgeLayer
    KnowledgeResult = hybrid_knowledge.KnowledgeResult
    mock_db = AsyncMock()

    with patch.object(HybridKnowledgeLayer, "_rule_search", new_callable=AsyncMock) as mock_rule:
        # Layer 1 returns borderline rule match (0.85 <= 0.9)
        mock_rule.return_value = [
            KnowledgeResult(id=1, content="borderline rule doc", confidence=0.85, source="rule")
        ]

        # RAG returns a better match
        with patch.object(HybridKnowledgeLayer, "_rag_search", new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = [
                KnowledgeResult(id=2, content="rag doc with higher fused rank", confidence=0.88, source="rag")
            ]

            layer = HybridKnowledgeLayer(db=mock_db)
            result = await layer.query("test query")

            # RRF should have been triggered (RAG was called)
            mock_rag.assert_called()
            assert result is not None
            # Result should come from rule or rag after RRF fusion
            assert result.source in ("rag", "rule"), \
                f"RRF result should come from rule or rag, got source='{result.source}'"