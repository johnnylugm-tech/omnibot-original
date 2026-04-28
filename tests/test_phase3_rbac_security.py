"""
Atomic TDD Tests for Phase 3: RBAC Security (#26)
Focus: Bearer Token Extraction, Privilege Escalation Prevention, and DELETE protection.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import Request, HTTPException
from app.security.rbac import RBACEnforcer

@pytest.fixture
def enforcer():
    return RBACEnforcer()

@pytest.mark.asyncio
async def test_id_26_01_secure_token_role_extraction(enforcer):
    """Verify role is extracted from Bearer token (simulated JWT)"""
    dependency = enforcer.require("knowledge", "read")
    
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"Authorization": "Bearer admin_token"}
    
    # Use patch.object for cleaner class method patching
    with patch.object(RBACEnforcer, "decode_token", return_value={"role": "admin"}):
        result = await dependency(mock_request)
        assert result == "admin"

@pytest.mark.asyncio
async def test_id_26_02_rbac_delete_requires_admin(enforcer):
    """Editor trying to DELETE knowledge -> 403"""
    dependency = enforcer.require("knowledge", "delete")
    
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"Authorization": "Bearer editor_token"}
    
    with patch.object(RBACEnforcer, "decode_token", return_value={"role": "editor"}):
        with pytest.raises(HTTPException) as exc:
            await dependency(mock_request)
        assert exc.value.status_code == 403
        assert "Authorization failed" in exc.value.detail

@pytest.mark.asyncio
async def test_id_26_03_token_tamper_detection(enforcer):
    """Invalid token format -> 401 Unauthorized"""
    dependency = enforcer.require("knowledge", "read")
    
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"Authorization": "Bearer invalid_token"}
    
    with patch.object(RBACEnforcer, "decode_token", side_effect=HTTPException(status_code=401, detail="Invalid token")):
        with pytest.raises(HTTPException) as exc:
            await dependency(mock_request)
        assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_id_26_04_missing_authorization_header(enforcer):
    """No Authorization header -> 401"""
    dependency = enforcer.require("knowledge", "read")
    
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    
    with pytest.raises(HTTPException) as exc:
        await dependency(mock_request)
    assert exc.value.status_code == 401
