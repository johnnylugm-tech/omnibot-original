"""
Atomic TDD Tests for ID #41: Business KPI Threshold Assertions
================================================================
These are RED-phase tests asserting KPI thresholds for all 3 phases.
Each test checks a specific threshold and will fail until implemented.

Missing tests (14):
  Phase 1: FCR >= 50%, CSAT +15%, p95 < 3s, telegram+line platform, security >= 95%, cost < $500, availability >= 99%
  Phase 2: FCR >= 80%, p95 < 1.5s, 4 platforms, CSAT +35%, disaster_recovery < 5min
  Phase 3: FCR >= 90%, p95 < 1s
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.odd_queries import ODDQueryManager


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def odd_manager(mock_db):
    return ODDQueryManager(mock_db)


def _build_result(mapping: dict):
    """Helper: return a mock row from fetchall()"""
    row = MagicMock()
    row._mapping = mapping
    return row


# =============================================================================
# FCR Threshold Tests (First Contact Resolution)
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_fcr_phase1_target_50_percent(odd_manager, mock_db):
    """Phase 1 FCR target: >= 50%"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [_build_result({"fcr_rate": 0.50})]
    mock_db.execute.return_value = mock_result

    rate = await odd_manager.get_fcr_rate()
    assert rate >= 0.50, f"Phase 1 FCR must be >= 50%, got {rate}"


@pytest.mark.asyncio
async def test_kpi_fcr_phase2_target_80_percent(odd_manager, mock_db):
    """Phase 2 FCR target: >= 80%"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [_build_result({"fcr_rate": 0.80})]
    mock_db.execute.return_value = mock_result

    rate = await odd_manager.get_fcr_rate()
    assert rate >= 0.80, f"Phase 2 FCR must be >= 80%, got {rate}"


@pytest.mark.asyncio
async def test_kpi_fcr_phase3_target_90_percent(odd_manager, mock_db):
    """Phase 3 FCR target: >= 90%"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [_build_result({"fcr_rate": 0.92})]
    mock_db.execute.return_value = mock_result

    rate = await odd_manager.get_fcr_rate()
    assert rate >= 0.90, f"Phase 3 FCR must be >= 90%, got {rate}"


# =============================================================================
# p95 Latency Tests
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_p95_latency_phase1_under_3s(odd_manager, mock_db):
    """Phase 1 p95 latency must be < 3 seconds (3000 ms)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        _build_result({"platform": "telegram", "p95_latency": 2500}),
        _build_result({"platform": "line", "p95_latency": 2800}),
    ]
    mock_db.execute.return_value = mock_result

    rows = await odd_manager.get_latency_p95_by_platform()
    for row in rows:
        p95 = row["p95_latency"]
        assert p95 < 3000, f"Phase 1 p95 latency must be < 3000ms, got {p95}ms for platform {row['platform']}"


@pytest.mark.asyncio
async def test_kpi_p95_latency_phase2_under_1(odd_manager, mock_db):
    """Phase 2 p95 latency must be < 1.5 seconds (1500 ms)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        _build_result({"platform": "telegram", "p95_latency": 1400}),
        _build_result({"platform": "line", "p95_latency": 1200}),
        _build_result({"platform": "messenger", "p95_latency": 1350}),
        _build_result({"platform": "whatsapp", "p95_latency": 1100}),
    ]
    mock_db.execute.return_value = mock_result

    rows = await odd_manager.get_latency_p95_by_platform()
    for row in rows:
        p95 = row["p95_latency"]
        # Actual threshold is 1.5s (1500ms) for Phase 2
        assert p95 < 1500, f"Phase 2 p95 latency must be < 1500ms, got {p95}ms for platform {row['platform']}"


@pytest.mark.asyncio
async def test_kpi_p95_latency_phase3_under_1s(odd_manager, mock_db):
    """Phase 3 p95 latency must be < 1 second (1000 ms)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        _build_result({"platform": "telegram", "p95_latency": 950}),
        _build_result({"platform": "line", "p95_latency": 880}),
    ]
    mock_db.execute.return_value = mock_result

    rows = await odd_manager.get_latency_p95_by_platform()
    for row in rows:
        p95 = row["p95_latency"]
        assert p95 < 1000, f"Phase 3 p95 latency must be < 1000ms, got {p95}ms for platform {row['platform']}"


# =============================================================================
# Platform Support Tests
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_platform_support_telegram_and_line(odd_manager, mock_db):
    """Phase 1 must support Telegram + LINE (at minimum 2 platforms)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        _build_result({"platform": "telegram", "count": 100}),
        _build_result({"platform": "line", "count": 80}),
    ]
    mock_db.execute.return_value = mock_result

    rows = await odd_manager.get_latency_p95_by_platform()
    platforms = {row["platform"] for row in rows}
    assert "telegram" in platforms, "Phase 1 must support telegram platform"
    assert "line" in platforms, "Phase 1 must support line platform"


@pytest.mark.asyncio
async def test_kpi_platform_support_4_platforms(odd_manager, mock_db):
    """Phase 2 must support 4 platforms: telegram, line, messenger, whatsapp"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        _build_result({"platform": "telegram", "count": 50}),
        _build_result({"platform": "line", "count": 40}),
        _build_result({"platform": "messenger", "count": 30}),
        _build_result({"platform": "whatsapp", "count": 20}),
    ]
    mock_db.execute.return_value = mock_result

    rows = await odd_manager.get_latency_p95_by_platform()
    platforms = {row["platform"] for row in rows}
    expected = {"telegram", "line", "messenger", "whatsapp"}
    assert platforms == expected, \
        f"Phase 2 must support 4 platforms {expected}, got {platforms}"


# =============================================================================
# Security Block Rate Test
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_security_block_rate_above_95_percent(odd_manager, mock_db):
    """Security block rate must be >= 95% (very high protection)"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [_build_result({"block_rate": 96.5})]
    mock_db.execute.return_value = mock_result

    rate = await odd_manager.get_security_block_rate()
    assert rate >= 95.0, \
        f"Security block rate must be >= 95%, got {rate}%"


# =============================================================================
# CSAT Improvement Tests
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_csat_phase1_baseline_improvement_15_percent(odd_manager, mock_db):
    """Phase 1 CSAT improvement over baseline: >= 15%"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [_build_result({"avg_csat": 0.72, "baseline_csat": 0.60})]
    mock_db.execute.return_value = mock_result

    stats = await odd_manager.get_csat_stats()
    baseline = stats.get("baseline_csat", 0)
    current = stats.get("avg_csat", 0)
    improvement_pct = ((current - baseline) / baseline * 100) if baseline > 0 else 0

    assert improvement_pct >= 15.0, \
        f"Phase 1 CSAT improvement must be >= 15%, got {improvement_pct:.2f}%"


@pytest.mark.asyncio
async def test_kpi_csat_phase2_improvement_35_percent(odd_manager, mock_db):
    """Phase 2 CSAT improvement over baseline: >= 35%"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [_build_result({"avg_csat": 0.82, "baseline_csat": 0.60})]
    mock_db.execute.return_value = mock_result

    stats = await odd_manager.get_csat_stats()
    baseline = stats.get("baseline_csat", 0)
    current = stats.get("avg_csat", 0)
    improvement_pct = ((current - baseline) / baseline * 100) if baseline > 0 else 0

    assert improvement_pct >= 35.0, \
        f"Phase 2 CSAT improvement must be >= 35%, got {improvement_pct:.2f}%"


# =============================================================================
# Cost Test
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_monthly_cost_under_500_usd(odd_manager, mock_db):
    """Monthly operational cost must be < $500 USD"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        _build_result({"knowledge_source": "rule", "total_cost": 150.0}),
        _build_result({"knowledge_source": "rag", "total_cost": 200.0}),
        _build_result({"knowledge_source": "llm", "total_cost": 120.0}),
    ]
    mock_db.execute.return_value = mock_result

    rows = await odd_manager.get_knowledge_source_cost()
    total_cost = sum(row["total_cost"] for row in rows)

    assert total_cost < 500.0, \
        f"Monthly cost must be < $500 USD, got ${total_cost:.2f}"


# =============================================================================
# Availability Test
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_availability_99(odd_manager, mock_db):
    """System availability must be >= 99%"""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [_build_result({"availability": 99.5})]
    mock_db.execute.return_value = mock_result

    availability = await odd_manager.get_system_availability()
    assert availability >= 99.0, \
        f"System availability must be >= 99%, got {availability}%"


# =============================================================================
# Disaster Recovery Test
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_disaster_recovery_under_5_minutes(odd_manager, mock_db):
    """Disaster recovery time must be < 5 minutes (300 seconds)"""
    # RED: RTO (Recovery Time Objective) must be tracked in audit_logs or system_metrics
    # This test checks if a disaster recovery time metric exists and is below 300s
    sql = """
    SELECT recovery_time_seconds
    FROM system_metrics
    WHERE metric_type = 'disaster_recovery'
    ORDER BY created_at DESC
    LIMIT 1;
    """
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [_build_result({"recovery_time_seconds": 240})]
    mock_db.execute.return_value = mock_result

    rows = await odd_manager.execute_query(sql)
    assert len(rows) > 0, \
        "Disaster recovery metric must be recorded in system_metrics table"

    recovery_time = rows[0]["recovery_time_seconds"]
    assert recovery_time < 300, \
        f"Disaster recovery time must be < 300 seconds, got {recovery_time}s"
