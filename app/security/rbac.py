"""RBAC (Role-Based Access Control) Enforcement - Phase 3"""

import base64
import hashlib
import hmac
import json
import os
from typing import Callable, Dict, List

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
        "experiment": ["read", "write"],
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

    # In production, use environment variable
    SECRET_KEY = os.getenv("OMNIBOT_SECRET_KEY", "prod_fallback_needs_env_var_override")

    def __init__(self, permissions: Dict[str, Dict[str, List[str]]] = ROLE_PERMISSIONS):
        self._permissions = permissions

    def create_token(self, role: str) -> str:
        """Helper for tests and trusted systems to create a signed token"""
        payload = {"role": role}
        payload_json = json.dumps(payload).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_json).decode().rstrip("=")

        signature = hmac.new(
            self.SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()

        return f"{payload_b64}.{signature}"

    def decode_token(self, token: str) -> dict:
        """
        Securely decode and validate the token signature.
        """
        try:
            parts = token.split(".")
            if len(parts) != 2:
                raise ValueError("Invalid token format")

            payload_b64, signature = parts

            # Verify signature
            expected_signature = hmac.new(
                self.SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError("Invalid signature")

            # Decode payload
            padding = "=" * (4 - len(payload_b64) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode()
            return json.loads(payload_json)

        except Exception:
            raise HTTPException(
                status_code=401,
                detail=("Could not validate credentials: Invalid or expired token"),
            )

    def check(self, role: str, resource: str, action: str) -> bool:
        """Verify if a role has permission for an action on a resource"""
        if not role:
            return False
        role_perms = self._permissions.get(role.lower(), {})
        allowed_actions = role_perms.get(resource.lower(), [])
        return action.lower() in allowed_actions

    def require(self, resource: str, action: str) -> Callable:
        """
        FastAPI dependency for RBAC.
        Now uses Secure Bearer Token.
        """

        async def rbac_dependency(request: Request) -> str:
            auth_header = request.headers.get("Authorization")

            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Missing or invalid Authorization header",
                )

            token = auth_header.replace("Bearer ", "")
            payload = self.decode_token(token)
            user_role = payload.get("role")

            if not user_role or not self.check(user_role, resource, action):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Authorization failed: Role '{user_role}' "
                        f"lacks '{action}' on '{resource}'"
                    ),
                )
            return user_role

        return rbac_dependency


# Singleton instance
rbac = RBACEnforcer()
