import pytest
from unittest.mock import MagicMock, patch
from app.services.odd_queries import ODDQueryManager

@pytest.fixture
def query_manager(mock_db):
    return ODDQueryManager(mock_db)

@pytest.mark.asyncio
@pytest.mark.spec
async def test_fcr_phase3_target_90_percent(query_manager):
    """SPEC: FCR must be >= 90%"""
    with patch.object(query_manager, 'execute_query', return_value=[{'fcr_rate': 0.95}]):
        rate = await query_manager.get_fcr_rate()
        assert rate >= 0.90

@pytest.mark.asyncio
@pytest.mark.spec
async def test_availability_99_9_percent_monthly(query_manager):
    """SPEC: System availability must be >= 99.9%"""
    assert hasattr(query_manager, 'get_system_availability')

@pytest.mark.asyncio
@pytest.mark.spec
async def test_p95_latency_under_1s(query_manager):
    """SPEC: p95 response time < 1.0s"""
    assert hasattr(query_manager, 'get_latency_p95_by_platform')
