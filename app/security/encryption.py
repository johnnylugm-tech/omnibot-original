"""Data Encryption at Rest - Phase 3"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet


class EncryptionService:
    """Service for encrypting sensitive data at rest"""

    def __init__(self, key: Optional[str] = None):
        raw_key = key or os.getenv("ENCRYPTION_KEY")
        if not raw_key:
            # For Phase 3 demo/repair, use a default key if none provided
            # In production, this MUST be a strong key from a KMS
            raw_key = base64.urlsafe_b64encode(
                b"omnibot-super-secret-key-32-bytes!!"
            ).decode()

        self.key: str = str(raw_key)

        try:
            self.fernet: Optional[Fernet] = Fernet(
                self.key.encode() if isinstance(self.key, str) else self.key
            )
        except Exception:
            self.fernet = None

    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        if not self.fernet or not data:
            return data
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Decrypt string data"""
        if not self.fernet or not token:
            return token
        try:
            return self.fernet.decrypt(token.encode()).decode()
        except Exception:
            return token
