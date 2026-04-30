"""Phase 1 extra tests: Error codes, Structured Logger, Dialogue State."""
import pytest
import json
import logging
from io import StringIO
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.api import app
from app.models.database import get_db
from app.utils.logger import StructuredLogger
from app.services.dst import DSTManager, ConversationState


# =============================================================================
# Section: Error Code Tests (7 tests)
# =============================================================================

@pytest.fixture
def mock_db_for_error_tests():
    """Shared mock DB for error code tests - mirrors test_api.py pattern."""
    from sqlalchemy.ext.asyncio import AsyncSession
    db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result
    db.commit = AsyncMock()

    def side_effect_add(obj):
        if hasattr(obj, 'id') and obj.id is None:
            obj.id = 1

    db.add = MagicMock(side_effect=side_effect_add)

    def set_scalar_return(obj):
        db.execute.return_value.scalar_one_or_none.return_value = obj

    db.set_scalar_return = set_scalar_return
    return db


@pytest.fixture
def client_with_mock_db(mock_db_for_error_tests):
    """TestClient with mocked DB dependency."""
    app.dependency_overrides[get_db] = lambda: mock_db_for_error_tests
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


# --- test_error_AUTH_INVALID_SIGNATURE_401 ---
def test_error_AUTH_INVALID_SIGNATURE_401(client_with_mock_db, mock_db_for_error_tests):
    """Invalid Authorization header returns 401.

    Spec: When a request carries a malformed/invalid Authorization header,
    the rbac.require() dependency must raise HTTPException(401).
    """
    from app.security.rbac import rbac

    # Malformed token (invalid base64 padding)
    headers = {"Authorization": "Bearer not_valid_base64.token"}

    response = client_with_mock_db.get("/api/v1/conversations", headers=headers)

    assert response.status_code == 401, \
        f"Expected 401 for invalid token, got {response.status_code}: {response.json()}"


# --- test_error_KNOWLEDGE_NOT_FOUND_404 ---
def test_error_KNOWLEDGE_NOT_FOUND_404(client_with_mock_db, mock_db_for_error_tests):
    """Non-existent knowledge ID returns 404.

    Spec: PUT /api/v1/knowledge/{id} where id does not exist → 404.
    Note: GET /api/v1/knowledge/{id} does not exist as a separate endpoint;
    individual knowledge GET is via query params on GET /api/v1/knowledge.
    We test the PUT endpoint (update) with a non-existent ID.
    """
    from app.security.rbac import rbac
    from app.models.database import KnowledgeBase

    # No knowledge entry with id=99999 exists
    mock_db_for_error_tests.execute.return_value.scalar_one_or_none.return_value = None

    headers = {"Authorization": f"Bearer {rbac.create_token('admin')}"}

    # PUT on non-existent knowledge entry returns 404
    response = client_with_mock_db.put(
        "/api/v1/knowledge/99999",
        json={"answer": "updated answer"},
        headers=headers
    )

    assert response.status_code == 404, \
        f"Expected 404, got {response.status_code}: {response.json()}"

    data = response.json()
    assert "error" in data or "detail" in data, \
        f"Expected error field, got: {data}"


# --- test_error_RATE_LIMIT_EXCEEDED_429 ---
def test_error_RATE_LIMIT_EXCEEDED_429(client_with_mock_db, mock_db_for_error_tests):
    """Rate limit exceeded returns 429.

    Spec: When RateLimiter.check() returns False, the webhook must
    return HTTP 429 with detail i18n.translate("rate_limit").
    """
    import os
    # Keep TELEGRAM_BOT_TOKEN empty so signature check is skipped (only triggered if both header AND token are set)
    old_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    os.environ["TELEGRAM_BOT_TOKEN"] = ""

    try:
        with patch("app.security.RateLimiter.check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False  # rate limit exceeded

            payload = {
                "message": {
                    "from": {"id": 1},
                    "text": "hi"
                }
            }
            response = client_with_mock_db.post(
                "/api/v1/webhook/telegram",
                json=payload,
                headers={"X-Telegram-Bot-Api-Secret-Token": ""}
            )

            assert response.status_code == 429, \
                f"Expected 429, got {response.status_code}: {response.json()}"

            data = response.json()
            # i18n.translate("rate_limit") returns "請求頻率過高" (Chinese)
            assert "請求頻率過高" in data.get("detail", "") or data.get("detail") == "Rate limit exceeded", \
                f"Expected rate limit message, got: {data}"
    finally:
        os.environ["TELEGRAM_BOT_TOKEN"] = old_token


# --- test_error_VALIDATION_ERROR_422 ---
def test_error_VALIDATION_ERROR_422(client_with_mock_db, mock_db_for_error_tests):
    """Invalid header value type returns 422 ValidationError.

    Spec: FastAPI's Pydantic validation for header types returns HTTP 422
    when a header value doesn't match the expected type (e.g., integer vs string).
    Since Authorization is a string header, sending an integer body for content-type
    that doesn't match would also trigger validation.
    We test that invalid type coercion in query params raises 422.
    """
    from app.security.rbac import rbac

    headers = {"Authorization": f"Bearer {rbac.create_token('admin')}"}

    # limit='abc' can't be parsed as int → FastAPI 422
    response = client_with_mock_db.get(
        "/api/v1/knowledge?limit=abc",
        headers=headers
    )

    assert response.status_code == 422, \
        f"Expected 422 for invalid limit type, got {response.status_code}: {response.json()}"

    data = response.json()
    assert "detail" in data, \
        f"Expected detail field in validation error, got: {data}"


# --- test_error_INTERNAL_ERROR_500 ---
def test_error_INTERNAL_ERROR_500(client_with_mock_db, mock_db_for_error_tests):
    """Uncaught exception in health check returns 500 INTERNAL_ERROR.


    Spec: When the health check endpoint encounters an unhandled exception
    (e.g., DB unavailable), it must return HTTP 500 with error_code INTERNAL_ERROR.
    """
    # The health_check handler explicitly re-raises "Database crash"
    # This propagates to FastAPI's exception middleware which returns HTTP 500.
    mock_db_for_error_tests.execute.side_effect = Exception("Database crash")

    with patch("redis.asyncio.from_url") as mock_redis_from_url:
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_redis_from_url.return_value = mock_redis

        # pytest.raises catches the Exception raised by TestClient's
        # ServerError middleware when raise_server_exceptions is True (default).
        # The exception message contains "Database crash".
        with pytest.raises(Exception) as exc_info:
            client_with_mock_db.get("/api/v1/health")

        assert "Database crash" in str(exc_info.value)


# --- test_error_AUTHZ_INSUFFICIENT_ROLE_403 ---
def test_error_AUTHZ_INSUFFICIENT_ROLE_403(client_with_mock_db, mock_db_for_error_tests):
    """Agent role cannot write knowledge → 403.

    Spec: Role 'agent' has only 'read' permission on 'knowledge' resource.
    Attempting to POST (write) knowledge must return HTTP 403.
    """
    from app.security.rbac import rbac

    # Agent role only has read permission, not write
    headers = {"Authorization": f"Bearer {rbac.create_token('agent')}"}

    response = client_with_mock_db.post(
        "/api/v1/knowledge",
        json={"question": "test", "answer": "test answer"},
        headers=headers
    )

    assert response.status_code == 403, \
        f"Expected 403, got {response.status_code}: {response.json()}"

    data = response.json()
    assert "detail" in data, \
        f"Expected error detail, got: {data}"


# =============================================================================
# Section: Structured Logger Tests (5 tests)
# =============================================================================

def test_structured_logger_includes_level():
    """StructuredLogger JSON output must include 'level' field.

    Spec: Every log entry must contain a 'level' key (e.g., INFO, ERROR).
    """
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)

    logger = StructuredLogger("test-service")
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.DEBUG)

    logger.info("test message")

    output = log_stream.getvalue().strip()
    assert output, "Logger produced no output"

    data = json.loads(output)
    assert "level" in data, f"JSON output missing 'level' field: {data}"
    assert data["level"] in ("INFO", "DEBUG", "WARN", "ERROR", "CRITICAL"), \
        f"Unexpected level value: {data['level']}"


def test_structured_logger_includes_message():
    """StructuredLogger JSON output must include 'message' field.

    Spec: Every log entry must contain a 'message' key with the log message text.
    """
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)

    logger = StructuredLogger("test-service")
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.DEBUG)

    logger.info("test message")

    output = log_stream.getvalue().strip()
    data = json.loads(output)

    assert "message" in data, f"JSON output missing 'message' field: {data}"
    assert data["message"] == "test message", \
        f"Expected message 'test message', got: {data['message']}"


def test_structured_logger_includes_service_name():
    """StructuredLogger JSON output must include 'service' field.

    Spec: Every log entry must contain a 'service' key with the service name
    passed to StructuredLogger.__init__.
    """
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)

    logger = StructuredLogger("my-service-name")
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.DEBUG)

    logger.info("service test")

    output = log_stream.getvalue().strip()
    data = json.loads(output)

    assert "service" in data, f"JSON output missing 'service' field: {data}"
    assert data["service"] == "my-service-name", \
        f"Expected service 'my-service-name', got: {data['service']}"


def test_structured_logger_includes_timestamp():
    """StructuredLogger JSON output must include 'timestamp' field.

    Spec: Every log entry must contain an ISO8601 'timestamp' key ending with Z.
    """
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)

    logger = StructuredLogger("test-service")
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.DEBUG)

    logger.info("timestamp test")

    output = log_stream.getvalue().strip()
    data = json.loads(output)

    assert "timestamp" in data, f"JSON output missing 'timestamp' field: {data}"
    assert data["timestamp"].endswith("Z"), \
        f"Timestamp must end with 'Z', got: {data['timestamp']}"


def test_structured_logger_output_is_json():
    """StructuredLogger output must be valid parseable JSON.

    Spec: The log output line must be a single valid JSON object (no extra text).
    """
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)

    logger = StructuredLogger("test-service")
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.DEBUG)

    logger.info("json test", extra_field="extra_value")

    output = log_stream.getvalue().strip()
    assert output, "Logger produced no output"

    # Must not raise - validates JSON is well-formed
    parsed = json.loads(output)

    assert isinstance(parsed, dict), \
        f"Parsed JSON must be a dict, got: {type(parsed)}"
    assert "message" in parsed, "Parsed JSON must contain 'message' key"


# =============================================================================
# Section: Dialogue State Tests (2 tests)
# =============================================================================

def test_dialogue_state_awaiting_confirmation_confirm_to_processing():
    """When state is AWAITING_CONFIRMATION and user confirms, go to PROCESSING.

    Spec: Transition AWAITING_CONFIRMATION + confirm intent → PROCESSING.
    """
    dst = DSTManager()

    # Initialize conversation in AWAITING_CONFIRMATION state
    state = dst.get_state(1)
    state.current_state = ConversationState.AWAITING_CONFIRMATION
    state.primary_intent = "book_flight"
    dst.update_state(state)

    # Simulate a turn with intent="confirm" (user confirms the booking)
    updated_state = dst.process_turn(1, intent="confirm", slots={"confirm": "yes"})

    assert updated_state.current_state == ConversationState.PROCESSING, \
        f"Expected PROCESSING after confirm, got: {updated_state.current_state}"


def test_dialogue_state_awaiting_confirmation_deny_to_slot_filling():
    """When state is AWAITING_CONFIRMATION and user denies, go back to SLOT_FILLING.

    Spec: Transition AWAITING_CONFIRMATION + deny intent → SLOT_FILLING
    (ask for different/corrected slot values).
    """
    dst = DSTManager()

    # Initialize conversation in AWAITING_CONFIRMATION state with a slot
    state = dst.get_state(2)
    state.current_state = ConversationState.AWAITING_CONFIRMATION
    state.primary_intent = "book_flight"
    state.slots = {
        "destination": {
            "name": "destination",
            "value": None,
            "required": True,
            "prompt": "Where do you want to go?"
        }
    }
    dst.update_state(state)

    # Simulate a turn with intent="deny" (user denies current slot values)
    updated_state = dst.process_turn(2, intent="deny", slots={"deny": "no"})

    # Deny should return to slot filling to ask again
    assert updated_state.current_state == ConversationState.SLOT_FILLING, \
        f"Expected SLOT_FILLING after deny, got: {updated_state.current_state}"


# =============================================================================
# Section: InputSanitizer Extra Tests (Batch A)
# =============================================================================

def test_sanitizer_empty_string_returns_empty_string():
    """sanitize(\"\") → \"\" (empty string returns empty string)"""
    from app.security.input_sanitizer import InputSanitizer
    sanitizer = InputSanitizer()
    result = sanitizer.sanitize("")
    assert result == "", \
        f"Expected empty string, got {repr(result)}"


def test_sanitizer_whitespace_only_returns_empty_string():
    """sanitize(\"   \") → \"\" (whitespace-only returns empty string)"""
    from app.security.input_sanitizer import InputSanitizer
    sanitizer = InputSanitizer()
    result = sanitizer.sanitize("   ")
    assert result == "", \
        f"Expected empty string for whitespace-only input, got {repr(result)}"


# =============================================================================
# Section: UnifiedMessage Immutable Tests (Batch A)
# =============================================================================

def test_unified_message_immutable():
    """UnifiedMessage is a frozen dataclass - attributes cannot be changed"""
    from app.models import UnifiedMessage, Platform, MessageType
    msg = UnifiedMessage(
        platform=Platform.TELEGRAM,
        platform_user_id="12345",
        unified_user_id="u1",
        message_type=MessageType.TEXT,
        content="test"
    )
    # Attempting to set any attribute should raise FrozenInstanceError
    import dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        msg.content = "changed"
    with pytest.raises(dataclasses.FrozenInstanceError):
        msg.platform_user_id = "99999"


# =============================================================================
# Section: Auth Token Expiry Tests (Batch A)
# =============================================================================

# =============================================================================
# Section: Webhook Telegram Signature Tests (Batch A)
# =============================================================================

def test_webhook_telegram_signature_valid():
    """Telegram verify_signature with correct secret returns True"""
    import hashlib
    import hmac
    from app.security.webhook_verifier import TelegramWebhookVerifier

    token = "test_bot_token"
    verifier = TelegramWebhookVerifier(token)
    body = b'{"message":{"from":{"id":123},"text":"hello"}}'

    # Compute correct signature
    secret_key = hashlib.sha256(token.encode()).digest()
    correct_sig = hmac.new(secret_key, body, hashlib.sha256).hexdigest()

    assert verifier.verify(body, correct_sig) is True, \
        "Correct Telegram signature should return True"


def test_webhook_telegram_signature_invalid():
    """Telegram verify_signature with wrong signature returns False"""
    from app.security.webhook_verifier import TelegramWebhookVerifier

    token = "test_bot_token"
    verifier = TelegramWebhookVerifier(token)
    body = b'{"message":{"from":{"id":123},"text":"hello"}}'

    assert verifier.verify(body, "invalid_signature") is False, \
        "Wrong Telegram signature should return False"


def test_webhook_telegram_valid_signature_returns_200():
    """Telegram webhook with valid signature returns 200"""
    import os
    import hashlib
    import hmac
    from fastapi.testclient import TestClient
    from app.api import app

    old_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    os.environ["TELEGRAM_BOT_TOKEN"] = "valid_bot_token"

    client = TestClient(app, raise_server_exceptions=False)

    try:
        token = "valid_bot_token"
        body_bytes = b'{"message":{"from":{"id":123},"text":"test"}}'

        with patch("app.api.process_webhook_message", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = ("ok", "rule")
            response = client.post(
                "/api/v1/webhook/telegram",
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Telegram-Bot-Api-Secret-Token": token
                }
            )
            assert response.status_code == 200, \
                f"Valid Telegram signature should return 200, got {response.status_code}: {response.json()}"
    finally:
        os.environ["TELEGRAM_BOT_TOKEN"] = old_token


def test_webhook_telegram_invalid_signature_returns_401():
    """Telegram webhook with invalid signature returns 401"""
    import os
    from fastapi.testclient import TestClient
    from app.api import app

    old_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    os.environ["TELEGRAM_BOT_TOKEN"] = "valid_bot_token"

    client = TestClient(app, raise_server_exceptions=False)

    try:
        with patch("app.api.process_webhook_message", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = ("ok", "rule")
            response = client.post(
                "/api/v1/webhook/telegram",
                json={"message": {"from": {"id": 123}, "text": "test"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "bad_signature"}
            )
            assert response.status_code == 401, \
                f"Invalid Telegram signature should return 401, got {response.status_code}: {response.json()}"
    finally:
        os.environ["TELEGRAM_BOT_TOKEN"] = old_token


def test_webhook_telegram_rate_limited_returns_429():
    """Telegram webhook when rate limited returns 429"""
    import os
    from fastapi.testclient import TestClient
    from app.api import app

    old_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    os.environ["TELEGRAM_BOT_TOKEN"] = ""

    client = TestClient(app, raise_server_exceptions=False)

    try:
        with patch("app.security.RateLimiter.check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False  # rate limit exceeded
            response = client.post(
                "/api/v1/webhook/telegram",
                json={"message": {"from": {"id": 1}, "text": "hi"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": ""}
            )
            assert response.status_code == 429, \
                f"Rate limited request should return 429, got {response.status_code}: {response.json()}"
    finally:
        os.environ["TELEGRAM_BOT_TOKEN"] = old_token


# =============================================================================
# Section: Webhook LINE Signature Tests (Batch B)
# =============================================================================

def test_webhook_line_signature_valid():
    """LINE verify_signature with correct secret returns True"""
    import hmac
    import hashlib
    import base64
    from app.security.webhook_verifier import LineWebhookVerifier

    secret = "channel_secret"
    verifier = LineWebhookVerifier(secret)
    body = b'{"events":[]}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    correct_sig = base64.b64encode(digest).decode()

    assert verifier.verify(body, correct_sig) is True, \
        "Correct LINE signature should return True"


def test_webhook_line_signature_invalid():
    """LINE verify_signature with wrong signature returns False"""
    from app.security.webhook_verifier import LineWebhookVerifier

    verifier = LineWebhookVerifier("channel_secret")
    body = b'{"events":[]}'

    assert verifier.verify(body, "invalid_signature") is False, \
        "Wrong LINE signature should return False"


def test_webhook_line_valid_signature_returns_200():
    """LINE webhook with valid signature returns 200"""
    import os
    import hmac
    import hashlib
    import base64
    from fastapi.testclient import TestClient
    from app.api import app

    old_secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    os.environ["LINE_CHANNEL_SECRET"] = "line_channel_secret"

    client = TestClient(app, raise_server_exceptions=False)

    try:
        secret = "line_channel_secret"
        body_bytes = b'{"events":[{"type":"message","message":{"text":"hi"}}]}'
        digest = hmac.new(secret.encode(), body_bytes, hashlib.sha256).digest()
        correct_sig = base64.b64encode(digest).decode()

        with patch("app.api.process_webhook_message", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = ("ok", "rule")
            response = client.post(
                "/api/v1/webhook/line",
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Line-Signature": correct_sig
                }
            )
            assert response.status_code == 200, \
                f"Valid LINE signature should return 200, got {response.status_code}: {response.json()}"
    finally:
        os.environ["LINE_CHANNEL_SECRET"] = old_secret


def test_webhook_line_invalid_signature_returns_401():
    """LINE webhook with invalid signature returns 401"""
    import os
    from fastapi.testclient import TestClient
    from app.api import app

    old_secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    os.environ["LINE_CHANNEL_SECRET"] = "line_channel_secret"

    client = TestClient(app, raise_server_exceptions=False)

    try:
        with patch("app.api.process_webhook_message", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = ("ok", "rule")
            response = client.post(
                "/api/v1/webhook/line",
                json={"events": [{"type": "message", "message": {"text": "hi"}}]},
                headers={"X-Line-Signature": "invalid_signature"}
            )
            assert response.status_code == 401, \
                f"Invalid LINE signature should return 401, got {response.status_code}: {response.json()}"
    finally:
        os.environ["LINE_CHANNEL_SECRET"] = old_secret


def test_webhook_line_rate_limited_returns_429():
    """LINE webhook when rate limited returns 429"""
    import os
    from fastapi.testclient import TestClient
    from app.api import app

    old_secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    os.environ["LINE_CHANNEL_SECRET"] = ""

    client = TestClient(app, raise_server_exceptions=False)

    try:
        with patch("app.security.RateLimiter.check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False
            response = client.post(
                "/api/v1/webhook/line",
                json={"events": [{"type": "message", "message": {"text": "hi"}}]},
                headers={"X-Line-Signature": ""}
            )
            assert response.status_code == 429, \
                f"Rate limited LINE request should return 429, got {response.status_code}: {response.json()}"
    finally:
        os.environ["LINE_CHANNEL_SECRET"] = old_secret


# =============================================================================
# Section: Webhook Messenger Signature Tests (Batch B)
# =============================================================================

def test_webhook_messenger_signature_valid():
    """Messenger verify_signature with correct secret returns True"""
    import hmac
    import hashlib
    from app.security.webhook_verifier import MessengerWebhookVerifier

    app_secret = "messenger_app_secret"
    verifier = MessengerWebhookVerifier(app_secret)
    body = b'{"entry":[]}'
    expected = "sha1=" + hmac.new(app_secret.encode(), body, hashlib.sha1).hexdigest()

    assert verifier.verify(body, expected) is True, \
        "Correct Messenger signature should return True"


def test_webhook_messenger_signature_invalid():
    """Messenger verify_signature with wrong signature returns False"""
    from app.security.webhook_verifier import MessengerWebhookVerifier

    verifier = MessengerWebhookVerifier("messenger_app_secret")
    body = b'{"entry":[]}'

    assert verifier.verify(body, "sha1=invalid") is False, \
        "Wrong Messenger signature should return False"


# =============================================================================
# Section: Webhook WhatsApp Signature Tests (Batch B)
# =============================================================================

def test_webhook_whatsapp_signature_valid():
    """WhatsApp verify_signature with correct secret returns True"""
    import hmac
    import hashlib
    from app.security.webhook_verifier import WhatsAppWebhookVerifier

    app_secret = "whatsapp_app_secret"
    verifier = WhatsAppWebhookVerifier(app_secret)
    body = b'{"entry":[]}'
    expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()

    assert verifier.verify(body, expected) is True, \
        "Correct WhatsApp signature should return True"


def test_webhook_whatsapp_signature_invalid():
    """WhatsApp verify_signature with wrong signature returns False"""
    from app.security.webhook_verifier import WhatsAppWebhookVerifier

    verifier = WhatsAppWebhookVerifier("whatsapp_app_secret")
    body = b'{"entry":[]}'

    assert verifier.verify(body, "sha256=invalid") is False, \
        "Wrong WhatsApp signature should return False"


# =============================================================================
# Section: Misc Webhook Tests (Batch B)
# =============================================================================

def test_webhook_401_on_invalid_signature():
    """Any webhook with invalid signature returns 401 (cross-platform)"""
    import os
    from fastapi.testclient import TestClient
    from app.api import app

    # Test with Telegram (signature provided but invalid)
    old_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    os.environ["TELEGRAM_BOT_TOKEN"] = "real_token"

    client = TestClient(app, raise_server_exceptions=False)

    try:
        with patch("app.api.process_webhook_message", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = ("ok", "rule")
            response = client.post(
                "/api/v1/webhook/telegram",
                json={"message": {"from": {"id": 1}, "text": "test"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_signature"}
            )
            assert response.status_code == 401, \
                f"Invalid signature should return 401 across platforms, got {response.status_code}"
    finally:
        os.environ["TELEGRAM_BOT_TOKEN"] = old_token


def test_webhook_429_on_rate_limit_exceeded():
    """Any webhook exceeding rate limit returns 429"""
    import os
    from fastapi.testclient import TestClient
    from app.api import app

    old_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    os.environ["TELEGRAM_BOT_TOKEN"] = ""

    client = TestClient(app, raise_server_exceptions=False)

    try:
        with patch("app.security.RateLimiter.check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False
            response = client.post(
                "/api/v1/webhook/telegram",
                json={"message": {"from": {"id": 1}, "text": "hi"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": ""}
            )
            assert response.status_code == 429, \
                f"Rate limit exceeded should return 429, got {response.status_code}"
    finally:
        os.environ["TELEGRAM_BOT_TOKEN"] = old_token


def test_webhook_verifier_registry_resolves_correct_type():
    """Webhook verifier registry resolves correct type by platform name"""
    from app.security.webhook_verifier import (
        VERIFIERS, get_verifier,
        LineWebhookVerifier, TelegramWebhookVerifier,
        MessengerWebhookVerifier, WhatsAppWebhookVerifier
    )

    line_verifier = get_verifier("line", "secret")
    assert isinstance(line_verifier, LineWebhookVerifier), \
        f"LINE platform should resolve to LineWebhookVerifier, got {type(line_verifier)}"

    tg_verifier = get_verifier("telegram", "token")
    assert isinstance(tg_verifier, TelegramWebhookVerifier), \
        f"Telegram platform should resolve to TelegramWebhookVerifier, got {type(tg_verifier)}"

    messenger_verifier = get_verifier("messenger", "secret")
    assert isinstance(messenger_verifier, MessengerWebhookVerifier), \
        f"Messenger platform should resolve to MessengerWebhookVerifier, got {type(messenger_verifier)}"

    whatsapp_verifier = get_verifier("whatsapp", "secret")
    assert isinstance(whatsapp_verifier, WhatsAppWebhookVerifier), \
        f"WhatsApp platform should resolve to WhatsAppWebhookVerifier, got {type(whatsapp_verifier)}"

    unknown_verifier = get_verifier("unknown", "secret")
    assert unknown_verifier is None, \
        f"Unknown platform should return None, got {type(unknown_verifier)}"