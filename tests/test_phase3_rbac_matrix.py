"""
Atomic TDD Tests for Phase 3: RBAC Full Permission Matrix (#25)
Focus: Exhaustive verification of all 4 roles (admin, editor, agent, auditor)
across all resources and actions as defined in Spec 25.
"""
import pytest
from app.security.rbac import RBACEnforcer

@pytest.fixture
def enforcer():
    return RBACEnforcer()

# Matrix: (role, resource, action, expected_allowed)
PERMISSION_MATRIX = [
    # Admin
    ("admin", "knowledge", "read", True),
    ("admin", "knowledge", "write", True),
    ("admin", "knowledge", "delete", True),
    ("admin", "escalate", "read", True),
    ("admin", "escalate", "write", True),
    ("admin", "experiment", "delete", True),
    ("admin", "system", "write", True),
    
    # Editor
    ("editor", "knowledge", "read", True),
    ("editor", "knowledge", "write", True),
    ("editor", "knowledge", "delete", False), # Cannot delete
    ("editor", "escalate", "read", True),
    ("editor", "escalate", "write", False), # Spec: ["read"]
    ("editor", "audit", "read", False), # Spec: []
    ("editor", "experiment", "read", True),
    
    # Agent
    ("agent", "knowledge", "read", True),
    ("agent", "knowledge", "write", False),
    ("agent", "escalate", "write", True), # Can write to queue
    ("agent", "escalate", "read", False), # Spec: ["write"] only
    ("agent", "conversations", "read", True),
    ("agent", "system", "read", False),
    
    # Auditor
    ("auditor", "knowledge", "read", True),
    ("auditor", "escalate", "read", True),
    ("auditor", "audit", "read", True),
    ("auditor", "system", "read", True),
    ("auditor", "knowledge", "write", False), # Read-only
    ("auditor", "experiment", "write", False),
]

@pytest.mark.parametrize("role, resource, action, expected", PERMISSION_MATRIX)
def test_id_25_matrix_enforcement(enforcer, role, resource, action, expected):
    """Verify role/resource/action against the expected outcome"""
    assert enforcer.check(role, resource, action) == expected

def test_id_25_case_insensitivity(enforcer):
    """Verify case insensitivity for role and action"""
    assert enforcer.check("ADMIN", "KNOWLEDGE", "READ") is True
    assert enforcer.check("Admin", "Knowledge", "Write") is True

def test_id_25_unknown_role_denied(enforcer):
    """Unknown roles should have no permissions"""
    assert enforcer.check("hacker", "knowledge", "read") is False
    assert enforcer.check("", "knowledge", "read") is False

def test_id_25_unknown_resource_denied(enforcer):
    """Unknown resources should be denied"""
    assert enforcer.check("admin", "secret_safe", "read") is False
