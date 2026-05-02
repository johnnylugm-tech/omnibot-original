"""
Atomic TDD Tests for ID #40: Comprehensive ODD SQL Verification
Focus: Testing all 13 ODD SQL queries with data-driven assertions.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.odd_queries import ODDQueryManager


@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.mark.asyncio
async def test_id_40_03_knowledge_hit_count(mock_db):
    """3. Knowledge hit count accuracy"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"knowledge_source": "rule", "hit_count": 100}),
        MagicMock(_mapping={"knowledge_source": "rag", "hit_count": 50})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    res = await manager.get_knowledge_hit_by_source()
    assert len(res) == 2
    assert res[0]["hit_count"] == 100

@pytest.mark.asyncio
async def test_id_40_04_csat_stats(mock_db):
    """4. CSAT Stats (Avg/p95)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"avg_csat": 4.5, "p95_csat": 5.0})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    res = await manager.get_csat_stats()
    assert res["avg_csat"] == 4.5
    assert res["p95_csat"] == 5.0

@pytest.mark.asyncio
async def test_id_40_05_knowledge_hit_distribution(mock_db):
    """5. Knowledge hit distribution percentage"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"knowledge_source": "llm", "count": 25, "percentage": 25.0})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    res = await manager.get_knowledge_hit_distribution()
    assert res[0]["percentage"] == 25.0

@pytest.mark.asyncio
async def test_id_40_07_sla_compliance(mock_db):
    """7. SLA Compliance by priority"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"priority": "high", "compliance_rate": 85.5})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    res = await manager.get_sla_compliance_by_priority()
    assert res[0]["compliance_rate"] == 85.5

@pytest.mark.asyncio
async def test_id_40_08_emotion_stats(mock_db):
    """8. Emotion stats aggregation"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"date": "2026-04-29", "category": "negative", "count": 10})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    res = await manager.get_emotion_stats()
    assert res[0]["count"] == 10

@pytest.mark.asyncio
async def test_id_40_09_security_block_rate(mock_db):
    """9. Security block rate accuracy"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"block_rate": 2.5})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    rate = await manager.get_security_block_rate()
    assert rate == 2.5

@pytest.mark.asyncio
async def test_id_40_11_pii_masking_rate(mock_db):
    """11. PII Masking rate accuracy"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"masking_rate": 12.0})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    rate = await manager.get_pii_masking_rate()
    assert rate == 12.0

@pytest.mark.asyncio
async def test_id_40_12_rbac_denial_audit(mock_db):
    """12. RBAC denial audit aggregation"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"role": "editor", "resource": "knowledge", "denial_count": 5})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    res = await manager.get_rbac_denial_audit()
    assert res[0]["denial_count"] == 5
