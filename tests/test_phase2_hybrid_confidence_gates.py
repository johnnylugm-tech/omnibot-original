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


# =============================================================================
# Section 44 G-03: LLM Layer 3 base prompt template in config
# =============================================================================

def test_llm_layer3_base_prompt_is_reproducible():
    """Base prompt template for LLM Layer 3 must exist in config. RED-phase test.
    
    Spec: The LLM Layer 3 (LLM generation) must use a base prompt template
    that is loaded from a configuration source (e.g., config file, environment
    variable, or database). This ensures reproducibility and allows changing
    the prompt without code changes.
    
    Current state: No such config exists. This test verifies the requirement
    that LLM Layer 3 loads its base prompt from a configuration source.
    """
    import os
    
    # Check if LLM Layer 3 base prompt config exists
    # It could be in various forms:
    # 1. Environment variable LLM_LAYER3_BASE_PROMPT
    # 2. A config file referenced by LLM_LAYER3_PROMPT_CONFIG path
    # 3. A database record
    
    base_prompt_config = os.getenv("LLM_LAYER3_BASE_PROMPT")
    prompt_config_path = os.getenv("LLM_LAYER3_PROMPT_CONFIG")
    
    has_config = base_prompt_config is not None or prompt_config_path is not None
    
    assert has_config, \
        "LLM Layer 3 base prompt template must be configurable via " \
        "LLM_LAYER3_BASE_PROMPT env var or LLM_LAYER3_PROMPT_CONFIG path. " \
        f"Got LLM_LAYER3_BASE_PROMPT={base_prompt_config}, " \
        f"LLM_LAYER3_PROMPT_CONFIG={prompt_config_path}"
    
    # If using a config file path, verify the file exists
    if prompt_config_path:
        assert os.path.isfile(prompt_config_path), \
            f"LLM_LAYER3_PROMPT_CONFIG points to non-existent file: {prompt_config_path}"
        
        # Verify it's a valid template (should contain placeholders)
        with open(prompt_config_path, 'r') as f:
            content = f.read()
        assert len(content) > 0, f"Prompt config file {prompt_config_path} is empty"
        # A proper template should have at least one placeholder like {query} or {context}
        assert '{' in content, \
            f"Prompt template should contain placeholders like {{query}}, got: {content[:100]}"


# =============================================================================
# LLM Layer Fall-through Tests (Batch A)
# =============================================================================

@pytest.mark.asyncio
async def test_hybrid_layer_llm_generate_returns_none_falls_through_to_layer4():
    """When _llm_generate() returns None, Layer 4 (escalate) takes over"""

    class NoLLMHybrid(HybridKnowledgeV7):
        async def _llm_generate(self, query, context):
            return None

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_result

    layer = NoLLMHybrid(db=mock_db)
    layer.llm = None

    with patch.dict(os.environ, {"SIMULATE_LLM": "false"}):
        result = await layer.query("test query with no LLM result")

    assert result is not None, "Query should always return a result"
    # When LLM returns None, it should fall through to escalate (Layer 4)
    assert result.source == "escalate", \
        f"LLM returns None → Layer 4 (escalate), got source='{result.source}'"
    assert result.id == -1, \
        f"Escalate result should have id=-1, got id={result.id}"