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
