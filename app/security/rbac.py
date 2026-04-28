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
        "conversations": ["read"],
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

    @staticmethod
    def decode_token(token: str) -> dict:
        """
        Placeholder for JWT decoding and validation.
        """
        if "invalid" in token:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        role = token.split("_")[0] if "_" in token else "unknown"
        return {"role": role}

    def check(self, role: str, resource: str, action: str) -> bool:
        """Verify if a role has permission for an action on a resource"""
        if not role: return False
        role_perms = self._permissions.get(role.lower(), {})
        allowed_actions = role_perms.get(resource.lower(), [])
        return action.lower() in allowed_actions

    def require(self, resource: str, action: str):
        """
        FastAPI dependency for RBAC.
        Now uses Bearer Token instead of X-User-Role header.
        """
        async def rbac_dependency(request: Request):
            auth_header = request.headers.get("Authorization")
            
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Missing or invalid Authorization header"
                )
            
            token = auth_header.replace("Bearer ", "")
            try:
                payload = self.decode_token(token)
                user_role = payload.get("role")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=401, detail="Could not validate credentials")
            
            if not user_role or not self.check(user_role, resource, action):
                raise HTTPException(
                    status_code=403,
                    detail=f"Authorization failed: Role '{user_role}' lacks '{action}' on '{resource}'"
                )
            return user_role
        return rbac_dependency


# Singleton instance
rbac = RBACEnforcer()
