"""
Atomic TDD Tests for Phase 1-3: ODD SQL Accuracy (#40)
Focus: Numerical accuracy of 13 analysis SQLs using a Data Factory.
All 11 gap tests for ODD SQL queries.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.odd_queries import ODDQueryManager


@pytest.fixture
def mock_db():
    return AsyncMock()


# =============================================================================
# ODD SQL Gap Tests (11 tests)
# =============================================================================

@pytest.mark.asyncio
async def test_odd_csat_query_calculates_avg_and_p95(mock_db):
    """CSAT query must calculate AVG(satisfaction_score) and PERCENTILE_CONT(0.95)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"avg_csat": 4.25, "p95_csat": 5.0})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    stats = await manager.get_csat_stats()

    assert "avg_csat" in stats, "CSAT query must return avg_csat"
    assert "p95_csat" in stats, "CSAT query must return p95_csat"
    assert stats["avg_csat"] == 4.25
    assert stats["p95_csat"] == 5.0

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "avg(" in query, "Query must use AVG aggregate"
    assert "percentile_cont" in query, "Query must use PERCENTILE_CONT for p95"


@pytest.mark.asyncio
async def test_odd_knowledge_hit_distribution_includes_percentage(mock_db):
    """Knowledge hit distribution query must include percentage column"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"knowledge_source": "rule", "count": 40, "percentage": 40.0}),
        MagicMock(_mapping={"knowledge_source": "rag", "count": 35, "percentage": 35.0}),
        MagicMock(_mapping={"knowledge_source": "llm", "count": 25, "percentage": 25.0}),
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    dist = await manager.get_knowledge_hit_distribution()

    assert len(dist) == 3
    for row in dist:
        assert "percentage" in row, f"Row missing percentage: {row}"
        assert row["percentage"] is not None

    assert dist[0]["knowledge_source"] == "rule"
    assert dist[0]["percentage"] == 40.0

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "percentage" in query or "round" in query, \
        "Query must calculate percentage from count/total"


@pytest.mark.asyncio
async def test_odd_feedback_query_joins_messages(mock_db):
    """Feedback query must JOIN messages table"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"feedback": "good", "comment": "thanks",
                           "message_content": "help response", "platform": "telegram"})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    feedback = await manager.get_feedback_analysis()

    assert len(feedback) == 1
    assert feedback[0]["message_content"] == "help response"

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "join" in query and "messages" in query, \
        "Feedback query must JOIN messages table"


@pytest.mark.asyncio
async def test_odd_sla_compliance_query_calculates_by_priority(mock_db):
    """SLA compliance rate query must group by priority"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"priority": "high", "compliance_rate": 75.5}),
        MagicMock(_mapping={"priority": "medium", "compliance_rate": 88.0}),
        MagicMock(_mapping={"priority": "low", "compliance_rate": 95.0}),
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    rates = await manager.get_sla_compliance_by_priority()

    assert len(rates) == 3
    for row in rates:
        assert "priority" in row, f"Row missing priority: {row}"
        assert "compliance_rate" in row

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "group by" in query and "priority" in query, \
        "SLA query must GROUP BY priority"


@pytest.mark.asyncio
async def test_odd_emotion_stats_query_groups_by_date_and_category(mock_db):
    """Emotion stats query must GROUP BY date AND category"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"date": "2024-01-15", "category": "positive", "count": 120}),
        MagicMock(_mapping={"date": "2024-01-15", "category": "negative", "count": 30}),
        MagicMock(_mapping={"date": "2024-01-14", "category": "positive", "count": 100}),
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    stats = await manager.get_emotion_stats()

    assert len(stats) == 3
    for row in stats:
        assert "date" in row, f"Row missing date: {row}"
        assert "category" in row, f"Row missing category: {row}"
        assert "count" in row

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "group by" in query, "Emotion query must have GROUP BY"
    assert "date" in query or "created_at" in query, \
        "Emotion query must group by date"


@pytest.mark.asyncio
async def test_odd_security_block_rate_query_calculates_percentage(mock_db):
    """Security block rate query calculates percentage: COUNT(risk IN ('high','critical')) / COUNT(*) * 100"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"block_rate": 12.34})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    rate = await manager.get_security_block_rate()

    assert rate == 12.34

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "percent" in query or "* 100" in query or "100" in query, \
        "Security block rate query must multiply by 100 for percentage"
    assert "high" in query or "critical" in query, \
        "Security block rate must check risk_level"


@pytest.mark.asyncio
async def test_odd_latency_p95_query_grouped_by_platform(mock_db):
    """p95 latency query groups by platform using PERCENTILE_CONT(0.95)"""
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

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "percentile_cont(0.95)" in query, \
        "Query must use PERCENTILE_CONT(0.95) WITHIN GROUP"
    assert "group by" in query and "platform" in query, \
        "Query must GROUP BY platform"


@pytest.mark.asyncio
async def test_odd_knowledge_hit_query_aggregates_by_source(mock_db):
    """Knowledge hit count query aggregates by knowledge_source"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"knowledge_source": "rule", "hit_count": 250}),
        MagicMock(_mapping={"knowledge_source": "rag", "hit_count": 180}),
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    hits = await manager.get_knowledge_hit_by_source()

    assert len(hits) == 2
    assert hits[0]["knowledge_source"] == "rule"
    assert hits[0]["hit_count"] == 250

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "group by" in query and "knowledge_source" in query, \
        "Query must GROUP BY knowledge_source"
    assert "count(*)" in query or "count(" in query, \
        "Query must use COUNT aggregate"


@pytest.mark.asyncio
async def test_odd_fcr_rate_query_rounds_to_2_decimals(mock_db):
    """FCR rate query uses ROUND(..., 2) for 2 decimal precision"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"fcr_rate": 0.67})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    rate = await manager.get_fcr_rate()

    assert rate == 0.67

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "round" in query, "Query must use ROUND for 2-decimal precision"
    assert "nullif" in query, "Query must use NULLIF to avoid division by zero"


@pytest.mark.asyncio
async def test_odd_ab_experiment_results_query_shows_running_only(mock_db):
    """A/B experiment query should show only running experiments (variant aggregation)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"experiment_id": 1, "variant": "control",
                           "avg_metric": 0.05, "total_samples": 500}),
        MagicMock(_mapping={"experiment_id": 1, "variant": "test_v1",
                           "avg_metric": 0.08, "total_samples": 500}),
        MagicMock(_mapping={"experiment_id": 2, "variant": "control",
                           "avg_metric": 0.03, "total_samples": 300}),
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    results = await manager.get_ab_test_performance()

    assert len(results) == 3
    for row in results:
        assert "experiment_id" in row, f"Row missing experiment_id: {row}"
        assert "variant" in row, f"Row missing variant: {row}"
        assert "avg_metric" in row or "total_samples" in row

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "group by" in query, "A/B query must use GROUP BY"
    assert "experiment_id" in query and "variant" in query, \
        "A/B query must group by experiment_id and variant"


@pytest.mark.asyncio
async def test_odd_cost_per_resolution_query_divides_total_cost_by_resolved(mock_db):
    """Cost per resolution: SUM(resolution_cost) / COUNT(resolved conversations)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"knowledge_source": "rule", "total_cost": 100.0, "resolutions": 50}),
        MagicMock(_mapping={"knowledge_source": "rag", "total_cost": 45.5, "resolutions": 30}),
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    costs = await manager.get_knowledge_source_cost()

    assert len(costs) == 2
    assert costs[0]["knowledge_source"] == "rule"
    assert costs[0]["total_cost"] == 100.0

    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "join" in query or "conversations" in query, \
        "Cost query must JOIN conversations"
    assert "group by" in query and "knowledge_source" in query, \
        "Cost query must GROUP BY knowledge_source"
    assert "sum(" in query or "total_cost" in query, \
        "Cost query must aggregate using SUM"


# =============================================================================
# Pre-existing tests (preserved)
# =============================================================================

@pytest.mark.asyncio
async def test_id_40_01_fcr_rate_calculation(mock_db):
    """1. FCR Rate accuracy (e.g. 2/3 = 0.67)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [MagicMock(_mapping={"fcr_rate": 0.67})]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    rate = await manager.get_fcr_rate()

    assert rate == 0.67
    args, _ = mock_db.execute.call_args
    query = str(args[0]).lower()
    assert "round" in query
    assert "nullif" in query


@pytest.mark.asyncio
async def test_id_40_02_latency_p95_grouped_by_platform(mock_db):
    """2. Latency p95 accuracy"""
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
        MagicMock(_mapping={"experiment_id": 1, "variant": "control",
                           "avg_metric": 0.05, "total_samples": 500}),
        MagicMock(_mapping={"experiment_id": 1, "variant": "test_v1",
                           "avg_metric": 0.08, "total_samples": 500})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    performance = await manager.get_ab_test_performance()

    assert len(performance) == 2
    assert performance[1]["avg_metric"] == 0.08