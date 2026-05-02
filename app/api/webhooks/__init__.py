"""Webhooks package — Phase 3 refactor from God File."""
from app.api.webhooks.telegram import router as telegram_router

__all__ = ["telegram_router"]
