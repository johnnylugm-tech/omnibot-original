"""RBAC (Role-Based Access Control) Enforcement - Phase 3"""
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from fastapi import HTTPException, Request

# Role and Permission mapping (Phase 3 spec)
ROLE_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    "admin": {
        "knowledge": ["read", "write", "delete"],
        "escalate": ["read", "write"],
        "audit": ["read"],
        "experiment": ["read", "write", "delete"],
        "system": ["read", "write"],
    },
    "editor": {
        "knowledge": ["read", "write"],
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
        role_perms = self._permissions.get(role.lower(), {})
        allowed_actions = role_perms.get(resource.lower(), [])
        return action.lower() in allowed_actions

    def require(self, resource: str, action: str):
        """Decorator to enforce RBAC on FastAPI endpoints"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract request from args or kwargs
                request = kwargs.get("request")
                if request is None:
                    for arg in args:
                        # Support both real Request objects and Mocks with headers attribute
                        if hasattr(arg, "headers"):
                            request = arg
                            break
                
                if request is None:
                    raise RuntimeError("RBAC decorator requires a Request object in arguments")

                # In Phase 3, role is typically extracted from a JWT token
                # For now, we look for X-User-Role header or default to None
                user_role = request.headers.get("X-User-Role")
                
                if not user_role or not self.check(user_role, resource, action):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Authorization failed: Role '{user_role}' lacks '{action}' on '{resource}'"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator


# Singleton instance
rbac = RBACEnforcer()
