"""
Atomic TDD Tests for Phase 3: RBAC Security (#26)
Focus: Bearer Token Extraction, Privilege Escalation Prevention, and DELETE protection.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

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

    with patch.object(
        RBACEnforcer,
        "decode_token",
        side_effect=HTTPException(status_code=401, detail="Invalid token"),
    ):
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


# =============================================================================
# S26 – Auth token expiry (Phase 3)
# =============================================================================


def test_token_expired_returns_401_auth_token_expired(
    client_with_mock_db, mock_db_for_error_tests
):
    """Expired or invalid auth token returns 401 with error_code AUTH_TOKEN_EXPIRED"""

    bad_token = "invalid.malformed.token"
    headers = {"Authorization": f"Bearer {bad_token}"}
    response = client_with_mock_db.get("/api/v1/knowledge", headers=headers)

    assert response.status_code == 401, (
        f"Expected 401 for invalid token, got {response.status_code}"
    )

    data = response.json()
    assert data.get("error_code") == "AUTH_TOKEN_EXPIRED", (
        f"Expected error_code AUTH_TOKEN_EXPIRED, got {data}"
    )


# =============================================================================
# Fixtures for token expiry tests (migrated from test_phase1_extra.py)
# =============================================================================


@pytest.fixture
def mock_db_for_error_tests():
    """Mock DB for error code tests."""
    from sqlalchemy.ext.asyncio import AsyncSession

    db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result
    db.commit = AsyncMock()

    def side_effect_add(obj):
        if hasattr(obj, "id") and obj.id is None:
            obj.id = 1

    db.add = MagicMock(side_effect=side_effect_add)
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def client_with_mock_db(mock_db_for_error_tests):
    """TestClient with overridden DB dependency."""
    from fastapi.testclient import TestClient

    from app.api import app
    from app.models.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db_for_error_tests
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()
