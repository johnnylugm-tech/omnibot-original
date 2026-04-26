"""Security layer for OmniBot Phase 1 - Webhook verification"""
import base64
import hashlib
import hmac
from abc import ABC, abstractmethod
from typing import Callable, Optional


class WebhookVerifier(ABC):
    @abstractmethod
    def verify(self, body: bytes, signature: str) -> bool:
        pass


class LineWebhookVerifier(WebhookVerifier):
    """LINE Webhook signature verifier"""
    def __init__(self, channel_secret: str):
        self.channel_secret = channel_secret.encode("utf-8")

    def verify(self, body: bytes, signature: str) -> bool:
        digest = hmac.new(
            self.channel_secret, body, hashlib.sha256
        ).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)


class TelegramWebhookVerifier(WebhookVerifier):
    """Telegram Webhook signature verifier"""
    def __init__(self, bot_token: str):
        self.secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()

    def verify(self, body: bytes, signature: str) -> bool:
        expected = hmac.new(
            self.secret_key, body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


class MessengerWebhookVerifier(WebhookVerifier):
    """Facebook Messenger Webhook signature verifier"""
    def __init__(self, app_secret: str):
        self.app_secret = app_secret.encode("utf-8")

    def verify(self, body: bytes, signature: str) -> bool:
        # Messenger uses sha1 (historical)
        expected = "sha1=" + hmac.new(
            self.app_secret, body, hashlib.sha1
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


class WhatsAppWebhookVerifier(WebhookVerifier):
    """WhatsApp Business API signature verifier"""
    def __init__(self, app_secret: str):
        self.app_secret = app_secret.encode("utf-8")

    def verify(self, body: bytes, signature: str) -> bool:
        # WhatsApp uses sha256
        expected = "sha256=" + hmac.new(
            self.app_secret, body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


VERIFIERS: dict[str, Callable[[str], WebhookVerifier]] = {
    "line": LineWebhookVerifier,
    "telegram": TelegramWebhookVerifier,
    "messenger": MessengerWebhookVerifier,
    "whatsapp": WhatsAppWebhookVerifier,
}


def get_verifier(platform: str, secret: str) -> Optional[WebhookVerifier]:
    """Factory function to get verifier by platform"""
    verifier_cls = VERIFIERS.get(platform.lower())
    if verifier_cls:
        return verifier_cls(secret)
    return None
