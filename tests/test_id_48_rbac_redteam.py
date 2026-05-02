"""
Atomic TDD Tests for ID #48: RBAC Red Team & Privilege Escalation
Focus: Token tampering, Role spoofing, and Unauthorized DELETE attempts.
"""

import pytest
from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_id_48_01_privilege_escalation_editor_to_delete():
    """RED: Editor trying to delete knowledge with forged token should fail"""
    # Current implementation allows "role_token" to be spoofed
    # We will simulate an editor trying to use an admin-like string if validation is weak  # noqa: E501
    response = client.delete(
        "/api/v1/knowledge/1", headers={"Authorization": "Bearer admin_spoof"}
    )

    # Expected: 401 if token is invalid/not signed, or 403 if role doesn't match
    # Since "admin_spoof" won't have a valid signature in the new impl, 401 is likely
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_id_48_02_token_tampering_malformed_json():
    """RED: Sending a non-JWT or malformed string should return 401"""
    response = client.get(
        "/api/v1/knowledge?q=test", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert response.status_code == 401
    assert "credentials" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_id_48_03_pii_luhn_non_card_numbers():
    """RED: Ensure 16-digit strings that FAIL Luhn are NOT masked"""
    from app.security.pii_masking import PIIMasking

    masker = PIIMasking()

    # A 16 digit number that fails Luhn
    fake_card = "1234567812345671"
    result = masker.mask(f"My ID is {fake_card}")

    assert fake_card in result.masked_text
    assert "[credit_card_masked]" not in result.masked_text
