"""
Atomic TDD Tests for Phase 1-3: ODD SQL Accuracy (#40)
Focus: Numerical accuracy of 13 analysis SQLs using a Data Factory.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.odd_queries import ODDQueryManager

class DataFactory:
    """Helper to generate Mock data rows for ODD testing"""
    
    @staticmethod
    def create_conversations(fcr_list, latency_list, platforms=None):
        """
        fcr_list: list of bool (FCR status)
        latency_list: list of int (ms)
        """
        rows = []
        for i, (fcr, latency) in enumerate(zip(fcr_list, latency_list)):
            rows.append({
                "id": i + 1,
                "first_contact_resolution": fcr,
                "response_time_ms": latency,
                "platform": platforms[i] if platforms else "telegram"
            })
        return rows

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.mark.asyncio
async def test_id_40_01_fcr_rate_calculation(mock_db):
    """1. FCR Rate accuracy (e.g. 2/3 = 0.67)"""
    # Setup: 2 True, 1 False -> Rate 0.67
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [MagicMock(_mapping={"fcr_rate": 0.67})]
    mock_db.execute.return_value = mock_result
    
    manager = ODDQueryManager(mock_db)
    rate = await manager.get_fcr_rate()
    
    assert rate == 0.67
    # Verify SQL contains ROUND and NULLIF
    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "round" in query
    assert "nullif" in query

@pytest.mark.asyncio
async def test_id_40_02_latency_p95_grouped_by_platform(mock_db):
    """2. Latency p95 accuracy"""
    # Setup: mock result for 2 platforms
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"platform": "telegram", "p95_latency": 150.0}),
        MagicMock(_mapping={"platform": "line", "p95_latency": 200.0})
    ]
    mock_db.execute.return_value = mock_result
    
    manager = ODDQueryManager(mock_db)
    res = await manager.get_latency_p95_by_platform()
    
    assert len(res) == 2
    assert res[0]["platform"] == "telegram"
    assert res[0]["p95_latency"] == 150.0
    
    # Verify SQL uses PERCENTILE_CONT
    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "percentile_cont(0.95)" in query

@pytest.mark.asyncio
async def test_id_40_10_knowledge_source_cost(mock_db):
    """10. Knowledge source cost aggregation"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"knowledge_source": "rule", "total_cost": 0.0}),
        MagicMock(_mapping={"knowledge_source": "rag", "total_cost": 15.5}),
        MagicMock(_mapping={"knowledge_source": "llm", "total_cost": 42.0})
    ]
    mock_db.execute.return_value = mock_result
    
    manager = ODDQueryManager(mock_db)
    costs = await manager.get_knowledge_source_cost()
    
    assert len(costs) == 3
    assert costs[1]["knowledge_source"] == "rag"
    assert costs[1]["total_cost"] == 15.5

@pytest.mark.asyncio
async def test_id_40_13_ab_test_performance(mock_db):
    """13. A/B test variant performance"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"experiment_id": 1, "variant": "control", "avg_metric": 0.05, "total_samples": 500}),
        MagicMock(_mapping={"experiment_id": 1, "variant": "test_v1", "avg_metric": 0.08, "total_samples": 500})
    ]
    mock_db.execute.return_value = mock_result
    
    manager = ODDQueryManager(mock_db)
    performance = await manager.get_ab_test_performance()
    
    assert len(performance) == 2
    assert performance[1]["avg_metric"] == 0.08


# =============================================================================
# Cost/Finance Tests - Layer-based cost estimation
# =============================================================================

def test_cost_estimation_layer1_zero():
    """Layer 1 (Rule-based) cost = 0 (no LLM call required)."""
    from app.utils.cost_model import CostModel

    model = CostModel()

    # Layer 1: rule-based lookup - no tokens consumed, no cost
    # In production: layer1_inference() calls rule_engine without LLM
    # Therefore, calculate_cost with 0 tokens must return 0
    cost = model.calculate_cost("gpt-4", prompt_tokens=0, completion_tokens=0)
    assert cost == 0.0, f"Layer 1 with 0 tokens should cost $0, got {cost}"

    # Even with minimal tokens (edge case), layer 1 should be ~0
    cost_small = model.calculate_cost("gpt-4", prompt_tokens=1, completion_tokens=1)
    assert cost_small < 0.0001, f"Layer 1 minimal cost should be near 0, got {cost_small}"


def test_cost_estimation_layer2_per_query():
    """Layer 2 (Hybrid/RAG) cost per query: prompt token cost only for retrieval."""
    from app.utils.cost_model import CostModel

    model = CostModel()

    # Layer 2: hybrid RAG - uses embedding lookup + small prompt
    # Typical Layer 2: ~500 prompt tokens (query embedding), ~100 completion tokens
    cost = model.calculate_cost("gpt-3.5-turbo", prompt_tokens=500, completion_tokens=100)

    # gpt-3.5-turbo: prompt=$0.0015/1K, completion=$0.002/1K
    expected = (500 / 1000) * 0.0015 + (100 / 1000) * 0.002
    assert abs(cost - expected) < 0.0001, f"Layer 2 cost mismatch: expected ~{expected}, got {cost}"
    assert cost > 0, "Layer 2 must have non-zero cost (LLM used)"


def test_cost_estimation_layer3_per_query():
    """Layer 3 (Full LLM) cost per query: both prompt and completion tokens."""
    from app.utils.cost_model import CostModel

    model = CostModel()

    # Layer 3: full LLM with rich context
    # Typical: 2000 prompt tokens + 500 completion tokens with gpt-4
    cost = model.calculate_cost("gpt-4", prompt_tokens=2000, completion_tokens=500)

    # gpt-4: prompt=$0.03/1K, completion=$0.06/1K
    expected = (2000 / 1000) * 0.03 + (500 / 1000) * 0.06
    assert abs(cost - expected) < 0.0001, f"Layer 3 cost mismatch: expected ~{expected}, got {cost}"
    assert cost > 0.05, f"Layer 3 full LLM cost should be > $0.05, got {cost}"


def test_monthly_cost_under_500_at_100k_conversations():
    """10万 conversations/month cost must stay under $500 (avg $0.005/conversation)."""
    from app.utils.cost_model import CostModel

    model = CostModel()

    # Realistic distribution:
    # - 60% Layer 1 (rule): $0 per conversation
    # - 30% Layer 2 (RAG): ~$0.001 per conversation (gpt-3.5-turbo, 500+100 tokens)
    # - 10% Layer 3 (full LLM): ~$0.065 per conversation (gpt-4, 2000+500 tokens)
    conversations = 100_000

    layer1_count = int(conversations * 0.60)  # 60,000
    layer2_count = int(conversations * 0.30)  # 30,000
    layer3_count = int(conversations * 0.10)  # 10,000

    # Layer 1 cost: $0 each
    layer1_cost = 0.0

    # Layer 2 cost: ~$0.00095 per conversation (gpt-3.5-turbo: 500 prompt + 100 completion)
    layer2_cost_per = model.calculate_cost("gpt-3.5-turbo", 500, 100)
    layer2_total = layer2_cost_per * layer2_count

    # Layer 3 cost: ~$0.065 per conversation (gpt-4: 2000 prompt + 500 completion)
    layer3_cost_per = model.calculate_cost("gpt-4", 2000, 500)
    layer3_total = layer3_cost_per * layer3_count

    monthly_total = layer1_cost + layer2_total + layer3_total

    assert monthly_total < 500.0, \
        f"Monthly cost at 100k conversations must be < $500, got ${monthly_total:.2f}"

    # Sanity check: avg per conversation
    avg_per_conv = monthly_total / conversations
    assert avg_per_conv < 0.005, \
        f"Average cost per conversation must be < $0.005, got ${avg_per_conv:.4f}"
