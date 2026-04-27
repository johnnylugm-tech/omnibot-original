"""RBAC (Role-Based Access Control) Enforcement - Phase 3"""
from typing import Any, Callable, Dict, List, Optional
from fastapi import HTTPException, Request

# Role and Permission mapping (Phase 3 spec)
ROLE_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    "admin": {
        "knowledge": ["read", "write", "delete"],
        "conversations": ["read", "write"],
        "escalate": ["read", "write"],
        "audit": ["read"],
        "experiment": ["read", "write", "delete"],
        "system": ["read", "write"],
    },
    "editor": {
        "knowledge": ["read", "write"],
        "conversations": ["read"],
        "escalate": ["read"],
        "audit": [],
        "experiment": ["read"],
        "system": [],
    },
    "agent": {
        "knowledge": ["read"],
        "escalate": ["write"],
        "audit": [],
        "experiment": [],
        "system": [],
    },
    "auditor": {
        "knowledge": ["read"],
        "conversations": ["read"],
        "escalate": ["read"],
        "audit": ["read"],
        "experiment": ["read"],
        "system": ["read"],
    },
}


class RBACEnforcer:
    """RBAC logic and FastAPI middleware/dependency helpers"""

    def __init__(self, permissions: Dict[str, Dict[str, List[str]]] = ROLE_PERMISSIONS):
        self._permissions = permissions

    def check(self, role: str, resource: str, action: str) -> bool:
        """Verify if a role has permission for an action on a resource"""
        if not role: return False
        role_perms = self._permissions.get(role.lower(), {})
        allowed_actions = role_perms.get(resource.lower(), [])
        return action.lower() in allowed_actions

    def require(self, resource: str, action: str):
        """
        FastAPI dependency for RBAC.
        Usage: user_role = Depends(rbac.require("resource", "action"))
        """
        async def rbac_dependency(request: Request):
            user_role = request.headers.get("X-User-Role")
            
            if not user_role or not self.check(user_role, resource, action):
                raise HTTPException(
                    status_code=403,
                    detail=f"Authorization failed: Role '{user_role}' lacks '{action}' on '{resource}'"
                )
            return user_role
        return rbac_dependency


# Singleton instance
rbac = RBACEnforcer()
