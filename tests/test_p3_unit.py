import pytest
from unittest.mock import AsyncMock, MagicMock
from app.security.rbac import RBACEnforcer
from app.services.ab_test import ABTestManager
from app.models.database import Experiment

@pytest.fixture
def rbac_enforcer():
    return RBACEnforcer()

# 4.2 Phase 3 驗證矩陣 - RBAC
class TestRBAC:
    def test_admin_permissions(self, rbac_enforcer):
        assert rbac_enforcer.check("admin", "knowledge", "write") is True
        assert rbac_enforcer.check("admin", "system", "delete") is False # admin doesn't have delete on system

    def test_agent_permissions(self, rbac_enforcer):
        assert rbac_enforcer.check("agent", "knowledge", "read") is True
        assert rbac_enforcer.check("agent", "knowledge", "write") is False
        assert rbac_enforcer.check("agent", "escalate", "write") is True

    @pytest.mark.asyncio
    async def test_rbac_decorator_blocking(self, rbac_enforcer):
        from fastapi import HTTPException
        
        @rbac_enforcer.require("knowledge", "write")
        async def protected_endpoint(request):
            return "success"
        
        # Mock request with insufficient role
        mock_request = MagicMock()
        mock_request.headers = {"X-User-Role": "agent"}
        
        with pytest.raises(HTTPException) as exc:
            await protected_endpoint(mock_request)
        assert exc.value.status_code == 403

# 4.2 Phase 3 驗證矩陣 - ABTest
class TestABTest:
    @pytest.mark.asyncio
    async def test_deterministic_assignment(self):
        mock_db = AsyncMock()
        manager = ABTestManager(db=mock_db)
        
        # Mock Experiment
        mock_exp = MagicMock(spec=Experiment)
        mock_exp.id = 1
        mock_exp.status = "running"
        mock_exp.traffic_split = {"control": 50, "test": 50}
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_exp
        mock_db.execute.return_value = mock_result
        
        # Same user should always get same variant
        v1 = await manager.get_variant("user_1", 1)
        v2 = await manager.get_variant("user_1", 1)
        assert v1 == v2
        
        # Different users might get different variants (depending on hash)
        v3 = await manager.get_variant("user_99", 1)
        # We don't assert v1 != v3 as they could hash to the same bucket, 
        # but we verified v1 == v2 which is the core deterministic property.
