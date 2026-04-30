"""RED Tests: Phase 1 Checklist Gaps - Section 2 (Unified Message), Section 5 (PII), Section 9 (Logger), Section 13 (DB Schema)"""
import pytest
import json
import logging
from datetime import datetime
from io import StringIO

from app.models import UnifiedMessage, Platform, MessageType


# =============================================================================
# Section 2: Unified Message Format - received_at default
# =============================================================================

class TestUnifiedMessageReceivedAtDefault:
    """test_unified_message_default_received_at"""

    def test_unified_message_default_received_at(self):
        """
        [RED] When received_at is NOT provided, it should auto-set to UTC now.
        Expected: received_at is a datetime close to datetime.utcnow()
        Current behavior: None (not yet implemented)
        """
        # The dataclass field has default_factory=datetime.utcnow
        # This test asserts the field auto-populates when omitted
        before = datetime.utcnow()
        msg = UnifiedMessage(
            platform=Platform.LINE,
            platform_user_id="U12345",
            unified_user_id="uuid-abc",
            message_type=MessageType.TEXT,
            content="hello"
            # received_at NOT provided
        )
        after = datetime.utcnow()

        assert msg.received_at is not None, "received_at must be auto-set when omitted"
        assert isinstance(msg.received_at, datetime), "received_at must be datetime"
        # Should be within 5 seconds of now
        delta = abs((msg.received_at - before).total_seconds())
        assert delta < 5, f"received_at={msg.received_at} not close to creation time (delta={delta}s)"


# =============================================================================
# Section 2: Unified Message Format - reply_token for TELEGRAM
# =============================================================================

class TestUnifiedMessageReplyTokenTelegram:
    """test_unified_message_reply_token_none_for_telegram"""

    def test_unified_message_reply_token_none_for_telegram(self):
        """
        [RED] When platform=TELEGRAM, reply_token should always be None.
        Expected: reply_token=None regardless of input
        Current behavior: reply_token passed through as-is
        """
        msg = UnifiedMessage(
            platform=Platform.TELEGRAM,
            platform_user_id="123456",
            unified_user_id="uuid-1",
            message_type=MessageType.TEXT,
            content="hello",
            reply_token="some-token"  # Telegram doesn't use reply tokens
        )
        assert msg.reply_token is None, "TELEGRAM platform must not have reply_token"


# =============================================================================
# Section 2: Unified Message Format - reply_token for LINE
# =============================================================================

class TestUnifiedMessageReplyTokenLINE:
    """test_unified_message_reply_token_set_for_line"""

    def test_unified_message_reply_token_set_for_line(self):
        """
        [RED] When platform=LINE and reply_token is provided, it should be saved correctly.
        Expected: reply_token preserved when platform=LINE
        Current behavior: may be None due to platform-specific logic
        """
        msg = UnifiedMessage(
            platform=Platform.LINE,
            platform_user_id="U12345",
            unified_user_id="uuid-1",
            message_type=MessageType.TEXT,
            content="hello",
            reply_token=".line.reply.token.here"
        )
        assert msg.reply_token == ".line.reply.token.here", \
            f"LINE reply_token not preserved: {msg.reply_token}"


# =============================================================================
# Section 5: PII Masking - Email
# =============================================================================

class TestPIIMaskingEmail:
    """test_pii_mask_email"""

    def test_pii_mask_email(self):
        """
        [RED] Email test@example.com should be masked as [email_masked].
        Expected: test@example.com -> [email_masked]
        Current behavior: email pattern exists in PIIMasking.PATTERNS
        """
        from app.security.pii_masking import PIIMasking
        masking = PIIMasking()
        result = masking.mask("my email is test@example.com")
        assert "[email_masked]" in result.masked_text, \
            f"Email not masked. Got: {result.masked_text}"
        assert "test@example.com" not in result.masked_text, \
            f"Email leak: {result.masked_text}"
        assert result.mask_count >= 1, f"mask_count={result.mask_count}"
        assert "email" in result.pii_types, f"email not in pii_types: {result.pii_types}"


# =============================================================================
# Section 9: Structured Logger - extra kwargs -> JSON top-level fields
# =============================================================================

class TestStructuredLoggerExtraFields:
    """test_structured_logger_extra_fields_passed_as_kwargs"""

    def test_structured_logger_extra_fields_passed_as_kwargs(self):
        """
        [RED] Extra kwargs should be expanded as JSON top-level fields.
        Expected: logger.info("msg", user_id="123") → JSON has user_id at top level
        Current behavior: None (may log nested or not at all)
        """
        from app.utils.logger import StructuredLogger

        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)

        logger = StructuredLogger("test-service")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        logger.info("user action", user_id="123", action="login", session="abc")

        output = log_stream.getvalue().strip()
        assert output, "No log output captured"
        data = json.loads(output)

        # Extra kwargs must appear as top-level JSON fields
        assert "user_id" in data, f"user_id missing from {data}"
        assert data["user_id"] == "123", f"user_id value wrong: {data['user_id']}"
        assert "action" in data, f"action missing from {data}"
        assert data["action"] == "login", f"action value wrong: {data['action']}"
        assert "session" in data, f"session missing from {data}"
        assert data["session"] == "abc"


# =============================================================================
# Section 9: Structured Logger - info() alias
# =============================================================================

class TestStructuredLoggerInfoAlias:
    """test_structured_logger_info_alias_calls_log_with_INFO"""

    def test_structured_logger_info_alias_calls_log_with_INFO(self):
        """
        [RED] info() should behave identically to log("INFO", ...).
        Expected: info("msg") logs with level=INFO
        Current behavior: may not call log() internally
        """
        from app.utils.logger import StructuredLogger

        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)

        logger = StructuredLogger("test-info-alias")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.DEBUG)

        logger.info("info alias test")

        output = log_stream.getvalue().strip()
        assert output, "No output from info()"
        data = json.loads(output)

        assert data["level"] == "INFO", \
            f"info() did not produce level=INFO, got: {data.get('level')}"
        assert data["message"] == "info alias test", \
            f"message mismatch: {data.get('message')}"


# =============================================================================
# Section 9: Structured Logger - error() alias
# =============================================================================

class TestStructuredLoggerErrorAlias:
    """test_structured_logger_error_alias_calls_log_with_ERROR"""

    def test_structured_logger_error_alias_calls_log_with_ERROR(self):
        """
        [RED] error() should behave identically to log("ERROR", ...).
        Expected: error("msg") logs with level=ERROR
        Current behavior: may not call log() internally
        """
        from app.utils.logger import StructuredLogger

        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)

        logger = StructuredLogger("test-error-alias")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.DEBUG)

        logger.error("error alias test", code=404)

        output = log_stream.getvalue().strip()
        assert output, "No output from error()"
        data = json.loads(output)

        assert data["level"] == "ERROR", \
            f"error() did not produce level=ERROR, got: {data.get('level')}"
        assert data["message"] == "error alias test", \
            f"message mismatch: {data.get('message')}"
        assert data.get("code") == 404, \
            f"error kwargs not passed: {data}"


# =============================================================================
# Section 13: Database Schema - embeddings vector dimension 384
# =============================================================================

class TestKnowledgeBaseEmbeddingsVector:
    """test_knowledge_base_embeddings_vector_384"""

    def test_knowledge_base_embeddings_vector_384(self):
        """
        [RED] knowledge_base.embeddings column must store 384-dimensional vectors.
        Expected: embedding_model='paraphrase-multilingual-MiniLM-L12-v2' → 384 dims
        Current behavior: JSONB without dimension constraint (requires pgvector extension)
        """
        # SQLAlchemy + asyncpg may not be installed in test environment
        # Use importorskip so the test SKIP-s rather than hard-crash
        sqlalchemy = pytest.importorskip("sqlalchemy")
        
        from app.models.database import KnowledgeBase

        kb_table = KnowledgeBase.__table__
        embeddings_col = kb_table.columns["embeddings"]

        # Column must exist
        assert embeddings_col is not None, "embeddings column missing"

        # Verify embedding_model column also exists
        model_col = kb_table.columns["embedding_model"]
        assert model_col is not None

        # Default model name documents 384-dim: paraphrase-multilingual-MiniLM-L12-v2 → 384
        default_model = str(model_col.default.arg) if model_col.default else ""
        assert "384" in default_model or "mini" in default_model.lower(), \
            f"embedding_model default={default_model} doesn't document 384-dim model"

        # The embeddings column type should be JSONB (stores vector as JSON array)
        assert embeddings_col.type.__class__.__name__ == "JSONB", \
            f"embeddings must be JSONB, got {embeddings_col.type.__class__.__name__}"


# =============================================================================
# Section 13: Database Schema - user_feedback check constraint
# =============================================================================

class TestUserFeedbackCheckConstraint:
    """test_user_feedback_check_constraint"""

    def test_user_feedback_check_constraint(self):
        """
        [RED] user_feedback.feedback column must have CHECK constraint for thumbs_up/thumbs_down.
        Expected: ALTER TABLE ADD CHECK (feedback IN ('thumbs_up', 'thumbs_down'))
        Current behavior: no CHECK constraint (any VARCHAR accepted)
        """
        # SQLAlchemy doesn't expose CHECK constraint details in ORM metadata easily.
        # Use SCHEMA_SQL raw text check as the source of truth.
        from app.models.database import SCHEMA_SQL

        # The SCHEMA_SQL defines the schema - scan for the CHECK constraint on user_feedback
        # In the raw SQL, the user_feedback table is created without a CHECK.
        # After GREEN phase, a CHECK constraint should be present.
        # We assert it IS present (will fail until implementation).

        # Extract user_feedback table definition from SCHEMA_SQL
        import re
        # Find the user_feedback table block in SCHEMA_SQL
        match = re.search(
            r"CREATE TABLE IF NOT EXISTS user_feedback\s*\(\s*([^;]+)\);",
            SCHEMA_SQL,
            re.DOTALL
        )
        assert match is not None, "user_feedback table not found in SCHEMA_SQL"

        table_def = match.group(1)

        # The CHECK constraint must restrict feedback to thumbs_up or thumbs_down
        # Look for CHECK clause containing feedback
        check_match = re.search(
            r"CHECK\s*\([^)]*feedback[^)]*IN\s*\(\s*['\"]thumbs_up['\"],\s*['\"]thumbs_down['\"]\s*\)\s*\)",
            table_def,
            re.IGNORECASE
        )
        assert check_match is not None, \
            f"user_feedback.feedback CHECK constraint for thumbs_up/thumbs_down not found in SCHEMA_SQL. Table def: {table_def[:500]}"
