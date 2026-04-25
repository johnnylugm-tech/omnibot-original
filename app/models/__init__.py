"""Data models for OmniBot Phase 1"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")


class Platform(Enum):
    TELEGRAM = "telegram"
    LINE = "line"
    MESSENGER = "messenger"  # Phase 2
    WHATSAPP = "whatsapp"  # Phase 2


class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    STICKER = "sticker"
    LOCATION = "location"
    FILE = "file"


@dataclass(frozen=True)
class UnifiedMessage:
    """Cross-platform unified message format (immutable)"""
    platform: Platform
    platform_user_id: str
    unified_user_id: Optional[str]
    message_type: MessageType
    content: str
    raw_payload: dict = field(default_factory=dict)
    received_at: datetime = field(default_factory=datetime.utcnow)
    reply_token: Optional[str] = None  # LINE specific


@dataclass(frozen=True)
class UnifiedResponse:
    """Unified response format"""
    content: str
    source: str  # rule | rag | wiki | escalate
    confidence: float
    knowledge_id: Optional[int] = None
    emotion_adjustment: Optional[str] = None  # Phase 2


@dataclass(frozen=True)
class KnowledgeResult:
    id: int
    content: str
    confidence: float
    source: str = ""  # rule | rag | wiki | escalate
    knowledge_id: Optional[int] = None


@dataclass(frozen=True)
class PIIMaskResult:
    masked_text: str
    mask_count: int
    pii_types: List[str]


@dataclass
class ApiResponse(Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class PaginatedResponse(ApiResponse[List[T]], Generic[T]):
    total: int = 0
    page: int = 1
    limit: int = 20
    has_next: bool = False


@dataclass(frozen=True)
class EscalationRequest:
    conversation_id: int
    reason: str  # no_rule_match | sensitive_content
