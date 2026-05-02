"""Shared application state for API module.

Avoids circular imports by centralizing mutable state in this single module.
All webhook handlers and route handlers import state from here.

Phase 3 refactor: extracted from app/api/__init__.py (God File)
"""
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AppState:
    """Application-wide service singletons and mutable shared state."""

    llm: Any = None
    db_pool: Any = None
    kb: Any = None
    emotion_analyzer: Any = None
    billing_tracker: Any = None
    emoji_sentiment: Any = None
    sentiment_tracker: Any = None
    emotion_history_repo: Any = None
    emotion_thresholds: Any = None
    emotion_decay: Any = None
    input_guard: Any = None
    output_guard: Any = None
    pii_masker: Any = None
    escalation: Any = None
    language_detector: Any = None
    i18n_cost_tracker: Any = None
    ab_test: Any = None

    # Mutable per-request tracking
    billable_messages: Dict = field(default_factory=dict)
    active_webhooks: Dict = field(default_factory=dict)


# Global singleton state instance — populated during FastAPI lifespan
state = AppState()
