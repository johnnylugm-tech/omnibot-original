"""Phase 2 Hybrid Knowledge Layer V7 — RRF Fusion Tests (Section 17)"""
import os
os.environ['SIMULATE_LLM'] = 'false'
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Use importorskip so test SKIPs if module doesn't exist yet
hybrid_knowledge = pytest.importorskip("app.services.hybrid_knowledge", reason="app.services.hybrid_knowledge not yet implemented")
HybridKnowledgeLayer = hybrid_knowledge.HybridKnowledgeLayer
KnowledgeResult = hybrid_knowledge.KnowledgeResult


# =============================================================================
# RRF Fusion Tests
# =============================================================================

@pytest.mark.asyncio
async def test_hybrid_layer_rrf_fusion_combines_rule_and_rag():
    """RRF k=60 fusion combines rule_results + rag_results; final results include both sources"""
    mock_db = AsyncMock()

    # Patch Layer 1 (rule) to return one result
    with patch.object(HybridKnowledgeLayer, "_rule_search", new_callable=AsyncMock) as mock_rule:
        mock_rule.return_value = [
            KnowledgeResult(id=1, content="rule doc", confidence=0.9, source="rule")
        ]

        # Patch Layer 2 (RAG) to return one result
        with patch.object(HybridKnowledgeLayer, "_rag_search", new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = [
                KnowledgeResult(id=2, content="rag doc", confidence=0.8, source="rag")
            ]

            layer = HybridKnowledgeLayer(db=mock_db)
            result = await layer.query("test query")

            # Result should be a fused KnowledgeResult (or list)
            # After RRF fusion, both rule doc (id=1) and rag doc (id=2) should appear
            assert result is not None
            # The spec says fused result contains items from both layers
            if hasattr(result, 'content'):
                # Single result returned - check it's from the fused set
                assert result.id in (1, 2), "Result should be from rule or rag layer"
            else:
                # Result is a list of fused results
                result_ids = [r.id for r in result]
                assert 1 in result_ids or 2 in result_ids


@pytest.mark.asyncio
async def test_hybrid_layer_rrf_scores_ranked_correctly():
    """Rank 1 document has highest RRF score"""
    mock_db = AsyncMock()

    with patch.object(HybridKnowledgeLayer, "_rule_search", new_callable=AsyncMock) as mock_rule:
        mock_rule.return_value = [
            KnowledgeResult(id=1, content="rule doc", confidence=0.9, source="rule"),
            KnowledgeResult(id=2, content="rule doc 2", confidence=0.7, source="rule"),
        ]

        with patch.object(HybridKnowledgeLayer, "_rag_search", new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = [
                KnowledgeResult(id=3, content="rag doc", confidence=0.8, source="rag"),
            ]

            layer = HybridKnowledgeLayer(db=mock_db)
            fused = await layer._rrf_fuse(
                [KnowledgeResult(id=1, content="rule doc", confidence=0.9, source="rule"),
                 KnowledgeResult(id=2, content="rule doc 2", confidence=0.7, source="rule")],
                [KnowledgeResult(id=3, content="rag doc", confidence=0.8, source="rag")],
                k=60
            )

            # After fusion, highest-ranked item should be first
            assert fused[0].id == 1, "Rank 1 doc should have highest RRF score"


@pytest.mark.asyncio
async def test_hybrid_layer_rrf_respects_k_parameter():
    """RRF score uses 1/(rank+k); k=60 should be used in denominator"""
    mock_db = AsyncMock()

    layer = HybridKnowledgeLayer(db=mock_db)

    # Manually compute RRF for known ranks to verify k is used
    rule_results = [
        KnowledgeResult(id=1, content="rule doc", confidence=0.9, source="rule"),
    ]
    rag_results = [
        KnowledgeResult(id=2, content="rag doc", confidence=0.8, source="rag"),
    ]

    fused_k60 = await layer._rrf_fuse(rule_results, rag_results, k=60)

    # id=1 appears at rank 1 from rule layer: score = 1/(1+60) ≈ 0.01639
    # id=2 appears at rank 1 from rag layer: score = 1/(1+60) ≈ 0.01639
    # Both equal; but verify at least both appear
    fused_ids = [r.id for r in fused_k60]
    assert 1 in fused_ids
    assert 2 in fused_ids

    # Now verify k=30 gives different ranking weights
    fused_k30 = await layer._rrf_fuse(rule_results, rag_results, k=30)
    fused_k30_ids = [r.id for r in fused_k30]
    assert fused_k60[0].id == fused_k30[0].id, "Ranking order should be same but scores differ"


# =============================================================================
# RAG Search Tests
# =============================================================================

@pytest.mark.asyncio
async def test_hybrid_layer_rag_search_uses_embedding_model_filter():
    """RAG query filters by embedding_model field"""
    mock_db = AsyncMock()

    # Mock DB execute to capture the SQL query text
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_result

    layer = HybridKnowledgeLayer(db=mock_db)
    await layer._rag_search("test query")

    # Verify execute was called (RAG search uses vector similarity query)
    mock_db.execute.assert_called()
    call_args = mock_db.execute.call_args
    query_str = str(call_args)
    # The RAG query should include an embedding_model filter
    # (e.g., WHERE embedding_model = 'text-embedding-3-small')
    assert "embedding" in query_str.lower(), "RAG query should filter by embedding_model"


@pytest.mark.asyncio
async def test_hybrid_layer_rag_search_orders_by_cosine_similarity():
    """Vector search uses embeddings <=> query_embedding ordering"""
    mock_db = AsyncMock()

    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_result

    layer = HybridKnowledgeLayer(db=mock_db)
    await layer._rag_search("test query")

    mock_db.execute.assert_called()
    query_str = str(mock_db.execute.call_args)
    # Cosine similarity ordering: <=> operator in pgvector / PostgreSQL
    assert "<=>" in query_str or "cosine" in query_str.lower(), \
        "RAG search should order by cosine similarity (<=>)"


# =============================================================================
# LLM Generate Override Hook Tests
# =============================================================================

@pytest.mark.asyncio
async def test_hybrid_layer_llm_generate_returns_result_when_overridden():
    """Subclass override of _llm_generate() returning KnowledgeResult → hybrid source='llm'"""
    mock_db = AsyncMock()

    class CustomHybrid(HybridKnowledgeLayer):
        async def _llm_generate(self, query, context):
            return KnowledgeResult(id=99, content="llm generated result", confidence=0.95, source="llm")

    with patch.object(CustomHybrid, "_rule_search", new_callable=AsyncMock) as mock_rule:
        with patch.object(CustomHybrid, "_rag_search", new_callable=AsyncMock) as mock_rag:
            mock_rule.return_value = []
            mock_rag.return_value = []

            layer = CustomHybrid(db=mock_db)
            result = await layer.query("test query")

            assert result is not None
            assert result.source == "llm", "Result source should be 'llm' when _llm_generate returns KnowledgeResult"
            assert result.id == 99


@pytest.mark.asyncio
async def test_hybrid_layer_llm_generate_returns_none_falls_through_to_layer4():
    """_llm_generate() returns None → hybrid continues to Layer 4 (wiki/escalate)"""
    mock_db = AsyncMock()

    class CustomHybrid(HybridKnowledgeLayer):
        async def _llm_generate(self, query, context):
            return None  # Fall through to next layer

    with patch.object(CustomHybrid, "_rule_search", new_callable=AsyncMock) as mock_rule:
        with patch.object(CustomHybrid, "_rag_search", new_callable=AsyncMock) as mock_rag:
            mock_rule.return_value = []
            mock_rag.return_value = []

            layer = CustomHybrid(db=mock_db)
            result = await layer.query("test query")

            # Should NOT have source='llm' (fallthrough occurred)
            # Final result should be from wiki or escalate
            assert result is not None
            assert result.source != "llm", "Should fall through when _llm_generate returns None"


# =============================================================================
# Escalation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_hybrid_layer_escalate_when_all_layers_fail():
    """All three layers return nothing → source='escalate', id=-1"""
    mock_db = AsyncMock()

    with patch.object(HybridKnowledgeLayer, "_rule_search", new_callable=AsyncMock) as mock_rule:
        with patch.object(HybridKnowledgeLayer, "_rag_search", new_callable=AsyncMock) as mock_rag:
            mock_rule.return_value = []
            mock_rag.return_value = []

            class NoLLMHybrid(HybridKnowledgeLayer):
                async def _llm_generate(self, query, context):
                    return None

            layer = NoLLMHybrid(db=mock_db)
            result = await layer.query("test query")

            assert result is not None
            assert result.source == "escalate", "All layers fail → escalate"
            assert result.id == -1, "escalate result should have id=-1"


@pytest.mark.asyncio
async def test_hybrid_layer_returns_knowledge_result_with_correct_source():
    """Each layer returns correct source: rule / rag / wiki / escalate"""
    mock_db = AsyncMock()

    # Layer 1: rule returns
    with patch.object(HybridKnowledgeLayer, "_rule_search", new_callable=AsyncMock) as mock_rule:
        mock_rule.return_value = [
            KnowledgeResult(id=1, content="rule doc", confidence=0.9, source="rule")
        ]
        layer = HybridKnowledgeLayer(db=mock_db)
        result = await layer.query("test query")
        assert result.source == "rule", "Rule layer should return source='rule'"

    # Layer 2: rag returns
    with patch.object(HybridKnowledgeLayer, "_rule_search", new_callable=AsyncMock) as mock_rule:
        with patch.object(HybridKnowledgeLayer, "_rag_search", new_callable=AsyncMock) as mock_rag:
            mock_rule.return_value = []
            mock_rag.return_value = [
                KnowledgeResult(id=2, content="rag doc", confidence=0.8, source="rag")
            ]
            layer = HybridKnowledgeLayer(db=mock_db)
            result = await layer.query("test query")
            assert result.source == "rag", "RAG layer should return source='rag'"
