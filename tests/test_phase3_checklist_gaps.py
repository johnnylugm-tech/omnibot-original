"""
Phase 3 TDD RED Tests — Additional Checklist Gaps
=================================================
These tests fill remaining Phase 3 checklist items that are not yet
covered (or not fully spec-compliant) in existing test files.
"""
import pytest
import tracemalloc
import time
import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock, patch
from prometheus_client import Gauge

# =============================================================================
# Observability — Prometheus Metrics (#29)
# =============================================================================

class TestPrometheusMetricsCombined:
    """Single test for gauge increment AND decrement cycle"""

    def test_metrics_conversation_active_gauge_increments_and_decrements(self):
        """Active conversations gauge increments then decrements back to baseline"""
        active_gauge = Gauge(
            "omnibot_test_active_conv_v4",
            "Active conversations for RED test",
            ["platform"]
        )

        initial = active_gauge.labels(platform="slack")._value.get()

        # Increment twice
        active_gauge.labels(platform="slack").inc()
        active_gauge.labels(platform="slack").inc()
        after_inc = active_gauge.labels(platform="slack")._value.get()
        assert after_inc == initial + 2

        # Decrement once
        active_gauge.labels(platform="slack").dec()
        after_dec = active_gauge.labels(platform="slack")._value.get()
        assert after_dec == initial + 1

# =============================================================================
# Cost Model (#38)
# =============================================================================

def test_cost_model_respects_daily_cap():
    """CostModel enforces daily cost cap — costs above cap are truncated"""
    from app.utils.cost_model import CostModel
    model = CostModel()

    # Signature: apply_daily_cap(self, current_total, next_cost, cap)
    # Case: Exceeds cap
    assert model.apply_daily_cap(current_total=8.0, next_cost=5.0, cap=10.0) == 2.0
    # Case: Already at cap
    assert model.apply_daily_cap(current_total=10.0, next_cost=5.0, cap=10.0) == 0.0
    # Case: Under cap
    assert model.apply_daily_cap(current_total=5.0, next_cost=2.0, cap=10.0) == 2.0

# =============================================================================
# ODD Queries (#40) — Knowledge Hit Distribution
# =============================================================================

@pytest.mark.asyncio
async def test_odd_knowledge_hit_distribution():
    """ODD knowledge distribution query returns hit rate per knowledge_source"""
    mod = pytest.importorskip("app.services.odd_queries")
    ODDQueryManager = mod.ODDQueryManager

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"knowledge_source": "rule", "count": 60, "percentage": 60.0}),
        MagicMock(_mapping={"knowledge_source": "rag",   "count": 30, "percentage": 30.0}),
        MagicMock(_mapping={"knowledge_source": "llm",   "count": 10, "percentage": 10.0}),
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    rows = await manager.get_knowledge_hit_distribution()

    assert len(rows) == 3
    by_source = {r["knowledge_source"]: r for r in rows}
    assert by_source["rule"]["percentage"] == 60.0

# =============================================================================
# KPI Thresholds (#41) — Security Block Rate
# =============================================================================

@pytest.mark.asyncio
async def test_kpi_security_block_rate():
    """Security block rate KPI fires alert when block_rate > 5%"""
    mod = pytest.importorskip("app.services.odd_queries")
    ODDQueryManager = mod.ODDQueryManager

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(_mapping={"block_rate": 6.5})
    ]
    mock_db.execute.return_value = mock_result

    manager = ODDQueryManager(mock_db)
    rate = await manager.get_security_block_rate()
    assert rate == 6.5
    assert rate > 5.0

# =============================================================================
# API Error Codes
# =============================================================================

def test_error_INTERNAL_ERROR_500():
    """Uncaught internal exception → HTTP 500 with error_code INTERNAL_ERROR"""
    try:
        from fastapi.testclient import TestClient
        from app.api import app
        client = TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI app not available")

    with patch("app.api.KPIManager.get_total_conversations", side_effect=Exception("Database crash")):
        from app.security.rbac import rbac
        token = rbac.create_token("admin")
        response = client.get("/api/v1/kpi/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 500
        assert response.json().get("error_code") == "INTERNAL_ERROR"

def test_error_AUTH_TOKEN_EXPIRED_401():
    """Expired/invalid Bearer token → HTTP 401 with error_code AUTH_TOKEN_EXPIRED"""
    try:
        from fastapi.testclient import TestClient
        from app.api import app
        client = TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI app not available")

    response = client.get("/api/v1/conversations", headers={"Authorization": "Bearer expired.token"})
    assert response.status_code == 401
    body = response.json()
    assert body.get("error_code") == "AUTH_TOKEN_EXPIRED"

# =============================================================================
# RBAC (#25) — agent escalate write exception
# =============================================================================

def test_rbac_agent_escalate_write_exception():
    """agent role can write escalate queue — Phase 3 exception"""
    from app.security.rbac import RBACEnforcer
    enforcer = RBACEnforcer()
    assert enforcer.check("agent", "escalate", "write") is True
    assert enforcer.check("auditor", "escalate", "write") is False

# =============================================================================
# A/B Testing (#27) — Traffic Allocation
# =============================================================================

@pytest.mark.asyncio
async def test_experiment_traffic_allocation_respects_split_percentages():
    """Traffic allocation matches traffic_split percentages precisely (±2% tolerance)"""
    mod = pytest.importorskip("app.services.ab_test")
    ABTestManager = mod.ABTestManager
    from uuid import uuid4

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_exp = MagicMock()
    mock_exp.id = 1
    mock_exp.status = "running"
    mock_exp.traffic_split = {"control": 30, "test_v1": 70}
    mock_result.scalar_one_or_none.return_value = mock_exp
    mock_db.execute.return_value = mock_result

    manager = ABTestManager(mock_db)
    variants = {"control": 0, "test_v1": 0}
    for i in range(1000):
        user_id = f"user_{i}_{uuid4()}"
        variant = await manager.get_variant(user_id, experiment_id=1)
        if variant in variants:
            variants[variant] += 1

    total = sum(variants.values())
    control_pct = variants["control"] / total * 100
    assert abs(control_pct - 30) <= 2
