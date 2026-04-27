import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import Request, HTTPException
from app.security.rbac import RBACEnforcer
from app.services.ab_test import ABTestManager
from app.utils.retry import RetryStrategy
import asyncio

# 1. RBAC Tests
def test_rbac_check():
    permissions = {
        "admin": {"knowledge": ["read", "write"]},
        "user": {"knowledge": ["read"]}
    }
    enforcer = RBACEnforcer(permissions)
    assert enforcer.check("admin", "knowledge", "write") is True
    assert enforcer.check("user", "knowledge", "write") is False
    assert enforcer.check("user", "knowledge", "read") is True

@pytest.mark.asyncio
async def test_rbac_dependency():
    enforcer = RBACEnforcer({"admin": {"system": ["read"]}})
    
    # Now it's a dependency, not a decorator
    dependency = enforcer.require("system", "read")

    # Mock success request
    mock_request_ok = MagicMock(spec=Request)
    mock_request_ok.headers = {"X-User-Role": "admin"}
    assert await dependency(mock_request_ok) == "admin"

    # Mock fail request
    mock_request_fail = MagicMock(spec=Request)
    mock_request_fail.headers = {"X-User-Role": "user"}
    with pytest.raises(HTTPException) as exc:
        await dependency(mock_request_fail)
    assert exc.value.status_code == 403

# 2. A/B Testing Tests
@pytest.mark.asyncio
async def test_ab_test_deterministic_variant():
    # Use explicit mock chain
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_exp = MagicMock()
    mock_exp.id = 1
    mock_exp.status = "running"
    mock_exp.traffic_split = {"control": 50, "variant_a": 50}
    
    # Chain: await db.execute() -> mock_result -> mock_result.scalar_one_or_none() -> mock_exp
    mock_db.execute.return_value = mock_result
    mock_result.scalar_one_or_none.return_value = mock_exp
    
    manager = ABTestManager(mock_db)
    
    # Same user should get same variant
    v1 = await manager.get_variant("user_123", 1)
    v2 = await manager.get_variant("user_123", 1)
    assert v1 == v2
    assert v1 in ["control", "variant_a"]

# 3. Retry Strategy Tests
@pytest.mark.asyncio
async def test_retry_strategy_success():
    strategy = RetryStrategy(max_retries=2, base_delay=0.01)
    mock_func = AsyncMock(return_value="done")
    
    result = await strategy.execute(mock_func)
    assert result == "done"
    assert mock_func.call_count == 1

@pytest.mark.asyncio
async def test_retry_strategy_failure():
    strategy = RetryStrategy(max_retries=2, base_delay=0.01)
    mock_func = AsyncMock(side_effect=Exception("fail"))
    
    with pytest.raises(Exception):
        await strategy.execute(mock_func)
    
    assert mock_func.call_count == 3 # 1 initial + 2 retries
