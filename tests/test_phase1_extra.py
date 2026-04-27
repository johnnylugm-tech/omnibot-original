import pytest
from datetime import datetime
from app.models import UnifiedMessage, Platform, MessageType
from app.utils.logger import StructuredLogger
import json
import logging
from io import StringIO

def test_unified_message_immutability():
    msg = UnifiedMessage(
        platform=Platform.TELEGRAM,
        platform_user_id="user123",
        unified_user_id=None,
        message_type=MessageType.TEXT,
        content="hello"
    )
    
    # Should be frozen
    with pytest.raises(AttributeError):
        msg.content = "new content"

def test_unified_message_defaults():
    msg = UnifiedMessage(
        platform=Platform.LINE,
        platform_user_id="line456",
        unified_user_id="uuid-1",
        message_type=MessageType.STICKER,
        content="sticker-id"
    )
    
    assert isinstance(msg.received_at, datetime)
    assert msg.raw_payload == {}
    assert msg.reply_token is None

def test_structured_logger_json_format():
    # Setup log capture
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = StructuredLogger("test-service")
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.INFO)
    
    logger.info("test message", user_id="123")
    
    output = log_stream.getvalue().strip()
    # Handle possible prefix from other handlers if any, but usually it's just the JSON
    # In our implementation, we log json.dumps(entry)
    data = json.loads(output)
    
    assert data["message"] == "test message"
    assert data["level"] == "INFO"
    assert data["service"] == "test-service"
    assert data["user_id"] == "123"
    assert "timestamp" in data
    assert data["timestamp"].endswith("Z")

def test_structured_logger_error_with_kwargs():
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = StructuredLogger("test-error")
    logger.logger.addHandler(handler)
    
    logger.error("failed operation", code=500, detail="db connection lost")
    
    data = json.loads(log_stream.getvalue().strip())
    assert data["level"] == "ERROR"
    assert data["code"] == 500
    assert data["detail"] == "db connection lost"
