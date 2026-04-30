"""
RED Gaps Verification - Phase 1
Focus: Reproducing reported RED FAILs in UnifiedMessage and Database Schema.
"""
import pytest
from app.models import UnifiedMessage, Platform, MessageType
from app.models.database import SCHEMA_SQL

def test_unified_message_reply_token_none_for_telegram():
    """test_id_01_02: UnifiedMessage 在 platform=TELEGRAM 時 reply_token 必須為 None"""
    msg = UnifiedMessage(
        platform=Platform.TELEGRAM,
        platform_user_id="tg123",
        unified_user_id=None,
        message_type=MessageType.TEXT,
        content="Hello",
        reply_token="should-be-cleared"  # Provide a token
    )
    # This should FAIL initially because the dataclass doesn't clear it
    assert msg.reply_token is None, "Telegram messages should not have a reply_token"

def test_user_feedback_check_constraint():
    """test_id_01_09: user_feedback 表必須有 CHECK 約束"""
    # The gap report states SCHEMA_SQL lacks the CHECK constraint
    # We search for the specific constraint string in the raw SQL
    expected_constraint = "CHECK (feedback IN ('thumbs_up','thumbs_down'))"
    
    # This should FAIL initially
    assert expected_constraint in SCHEMA_SQL, "user_feedback table missing CHECK constraint for feedback values"
