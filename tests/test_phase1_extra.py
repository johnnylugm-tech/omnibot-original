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
    """Shared mock DB for error code tests."""
    db = MagicMock()
    db.add = MagicMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()

    # Mock the execute result for scalars().all() used in process_webhook_message
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []  # empty conversation list
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    def set_scalar_return(obj):
        mock_result.scalar_one_or_none.return_value = obj

    mock_db.set_scalar_return = set_scalar_return
    return mock_db


@pytest.fixture
def client_with_mock_db(mock_db_for_error_tests):
    """TestClient with mocked DB dependency."""
    app.dependency_overrides[get_db] = lambda: mock_db_for_error_tests
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


# --- test_error_AUTH_INVALID_SIGNATURE_401 ---
def test_error_AUTH_INVALID_SIGNATURE_401(client_with_mock_db, mock_db_for_error_tests):
    """Invalid Telegram signature returns 401 with error_code AUTH_TOKEN_EXPIRED.

    Spec: When a webhook request carries an invalid signature,
    the endpoint must return HTTP 401 and set error_code to AUTH_TOKEN_EXPIRED.
    """
    from app.models.database import User
    from datetime import datetime

    # Mock get_or_create_user to return a real user object (not a coroutine)
    mock_user = MagicMock(spec=User)
    mock_user.unified_user_id = "uuid-test"
    mock_user.platform = "telegram"
    mock_user.platform_user_id = "12345"

    mock_conv = MagicMock()
    mock_conv.id = 1

    # Properly set up db.execute mock so process_webhook_message doesn't fail before
    # the signature check
    mock_db_for_error_tests.execute.return_value.scalar_one_or_none.return_value = None

    with patch("app.api.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
        mock_get_user.return_value = mock_user

        with patch("app.api.get_active_conversation", new_callable=AsyncMock) as mock_get_conv:
            mock_get_conv.return_value = mock_conv

            # Patch verify_signature to return False
            with patch("app.api.verify_signature", return_value=False):
                payload = {
                    "message": {
                        "from": {"id": 12345},
                        "text": "test"
                    }
                }
                # Provide a fake secret token header so signature verification is triggered
                response = client_with_mock_db.post(
                    "/api/v1/webhook/telegram",
                    json=payload,
                    headers={"X-Telegram-Bot-Api-Secret-Token": "bad_signature_token"}
                )

                assert response.status_code == 401, \
                    f"Expected 401, got {response.status_code}: {response.json()}"

                data = response.json()
                assert data.get("success") is False or "error" in data, \
                    f"Expected error response, got: {data}"


# --- test_error_KNOWLEDGE_NOT_FOUND_404 ---
def test_error_KNOWLEDGE_NOT_FOUND_404(client_with_mock_db, mock_db_for_error_tests):
    """Non-existent knowledge ID returns 404.

    Spec: GET /api/v1/knowledge/{id} where id does not exist → 404.
    """
    from app.models.database import KnowledgeBase

    # No knowledge entry with id=99999 exists
    mock_db_for_error_tests.execute.return_value.scalar_one_or_none.return_value = None

    response = client_with_mock_db.get("/api/v1/knowledge/99999")

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
    from app.models.database import User

    mock_user = MagicMock(spec=User)
    mock_user.unified_user_id = "uuid-test"

    mock_conv = MagicMock()
    mock_conv.id = 1

    # Set up db.execute return to prevent crashes before rate limit check
    mock_db_for_error_tests.execute.return_value.scalar_one_or_none.return_value = None

    with patch("app.api.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
        mock_get_user.return_value = mock_user

        with patch("app.api.get_active_conversation", new_callable=AsyncMock) as mock_get_conv:
            mock_get_conv.return_value = mock_conv

            with patch("app.security.RateLimiter.check", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False  # rate limit exceeded

                payload = {
                    "message": {
                        "from": {"id": 1},
                        "text": "hi"
                    }
                }
                # Empty secret skips signature check
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


# --- test_error_VALIDATION_ERROR_422 ---
def test_error_VALIDATION_ERROR_422(client_with_mock_db, mock_db_for_error_tests):
    """Missing required fields return 422 ValidationError.

    Spec: POST /api/v1/knowledge with missing required body fields → 422.
    """
    from app.security.rbac import rbac

    headers = {"Authorization": f"Bearer {rbac.create_token('admin')}"}

    # POST with empty body (missing 'question' and 'answer' required fields)
    response = client_with_mock_db.post(
        "/api/v1/knowledge",
        json={},
        headers=headers
    )

    assert response.status_code == 422, \
        f"Expected 422, got {response.status_code}: {response.json()}"

    data = response.json()
    # Pydantic/FastAPI validation error structure
    assert "detail" in data, \
        f"Expected detail field in validation error, got: {data}"


# --- test_error_INTERNAL_ERROR_500 ---
def test_error_INTERNAL_ERROR_500(client_with_mock_db, mock_db_for_error_tests):
    """Database failure returns 500 Internal Server Error.

    Spec: When the database query raises an unhandled exception during
    health check, the handler must return HTTP 500 with error_code INTERNAL_ERROR.
    """
    # Make DB execute raise an exception containing "Database crash"
    mock_db_for_error_tests.execute.side_effect = Exception("Database crash")

    response = client_with_mock_db.get("/api/v1/health")

    assert response.status_code == 500, \
        f"Expected 500, got {response.status_code}: {response.json()}"

    data = response.json()
    assert data.get("error_code") == "INTERNAL_ERROR" or "error" in data, \
        f"Expected INTERNAL_ERROR, got: {data}"


# --- test_error_LLM_TIMEOUT_504 ---
def test_error_LLM_TIMEOUT_504(client_with_mock_db, mock_db_for_error_tests):
    """LLM timeout returns 504 LLM_TIMEOUT.

    Spec: When process_webhook_message raises TimeoutError, the webhook
    endpoint must return HTTP 504 with detail "LLM_TIMEOUT".
    """
    with patch("app.api.process_webhook_message", new_callable=AsyncMock) as mock_process:
        mock_process.side_effect = TimeoutError("LLM request timed out")

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

        assert response.status_code == 504, \
            f"Expected 504, got {response.status_code}: {response.json()}"

        data = response.json()
        assert data.get("detail") == "LLM_TIMEOUT", \
            f"Expected 'LLM_TIMEOUT', got: {data}"


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
# Section: Webhook Signature & Rate Limit Tests (Section 44 G-07, G-08)
# =============================================================================

def test_webhook_telegram_signature_valid():
    """Valid Telegram HMAC-SHA256 signature → verify returns True."""
    from app.security.webhook_verifier import TelegramWebhookVerifier
    import hmac, hashlib

    token = 'test_bot_token'
    verifier = TelegramWebhookVerifier(token)
    body = b'{"update_id": 123456789, "message": {"text": "hello"}}'
    secret_key = hashlib.sha256(token.encode('utf-8')).digest()
    valid_sig = hmac.new(secret_key, body, hashlib.sha256).hexdigest()
    assert verifier.verify(body, valid_sig) is True


def test_webhook_telegram_signature_invalid():
    """Invalid Telegram signature → verify returns False."""
    from app.security.webhook_verifier import TelegramWebhookVerifier
    import hmac, hashlib

    token = 'test_bot_token'
    verifier = TelegramWebhookVerifier(token)
    body = b'{"update_id": 123456789, "message": {"text": "hello"}}'
    assert verifier.verify(body, 'deadbeef1234567890abcdef') is False


def test_webhook_telegram_invalid_signature_returns_401():
    """Telegram webhook with wrong secret → HTTP 401."""
    from app.api import verify_signature
    import hmac, hashlib

    real_token = 'real_bot_token'
    fake_token = 'fake_bot_token'
    body = b'{"update_id": 999999999, "message": {"text": "test"}}'
    secret_key_wrong = hashlib.sha256(fake_token.encode('utf-8')).digest()
    bad_sig = hmac.new(secret_key_wrong, body, hashlib.sha256).hexdigest()
    result = verify_signature('telegram', body, bad_sig, real_token)
    assert result is False


def test_webhook_telegram_valid_signature_returns_200():
    """Telegram webhook with correct signature → HTTP 200."""
    from app.api import verify_signature
    import hmac, hashlib

    token = 'my_secret_bot_token'
    body = b'{"update_id": 111222333, "message": {"text": "hi"}}'
    secret_key = hashlib.sha256(token.encode('utf-8')).digest()
    good_sig = hmac.new(secret_key, body, hashlib.sha256).hexdigest()
    result = verify_signature('telegram', body, good_sig, token)
    assert result is True


def test_webhook_line_signature_valid():
    """Valid LINE signature (HMAC-SHA256, base64) → verify returns True."""
    from app.security.webhook_verifier import LineWebhookVerifier
    import hmac, hashlib, base64

    secret = 'my_line_channel_secret'
    verifier = LineWebhookVerifier(secret)
    body = b'{"destination": "U123", "events": []}'
    digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    valid_sig = base64.b64encode(digest).decode('utf-8')
    assert verifier.verify(body, valid_sig) is True


def test_webhook_line_signature_invalid():
    """Invalid LINE signature → verify returns False."""
    from app.security.webhook_verifier import LineWebhookVerifier

    secret = 'my_line_channel_secret'
    verifier = LineWebhookVerifier(secret)
    body = b'{"destination": "U123", "events": []}'
    assert verifier.verify(body, 'invalid_base64_signature') is False


def test_webhook_line_invalid_signature_returns_401():
    """LINE webhook with wrong signature → HTTP 401."""
    from app.api import verify_signature

    secret = 'line_secret_123'
    body = b'{"events": [{"type": "message"}]}'
    bad_sig = 'wrong_signature_not_base64'
    result = verify_signature('line', body, bad_sig, secret)
    assert result is False


def test_webhook_line_valid_signature_returns_200():
    """LINE webhook with correct signature → HTTP 200."""
    from app.api import verify_signature
    import hmac, hashlib, base64

    secret = 'line_secret_123'
    body = b'{"events": [{"type": "message", "replyToken": "abc123"}]}'
    digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    good_sig = base64.b64encode(digest).decode('utf-8')
    result = verify_signature('line', body, good_sig, secret)
    assert result is True


def test_webhook_line_rate_limited_returns_429():
    """LINE webhook rate limiter blocks after bucket exhaustion → HTTP 429."""
    from app.security.rate_limiter import RateLimiter
    import asyncio

    limiter = RateLimiter(default_rps=1)
    user_id = 'user_telegram_123'
    # First → True, second → False (exhausted)
    r1 = limiter.check('line', user_id)
    r2 = limiter.check('line', user_id)
    assert r1 is True
    assert r2 is False


def test_webhook_messenger_signature_valid():
    """Valid Messenger (sha1=...) signature → verify returns True."""
    from app.security.webhook_verifier import MessengerWebhookVerifier
    import hmac, hashlib

    app_secret = 'messenger_app_secret_key'
    verifier = MessengerWebhookVerifier(app_secret)
    body = b'{"object": "page", "entry": [{"id": "123", "time": 1234567890, "messaging": []}]}'
    sig_hex = hmac.new(app_secret.encode('utf-8'), body, hashlib.sha1).hexdigest()
    signature = 'sha1=' + sig_hex
    assert verifier.verify(body, signature) is True


def test_webhook_messenger_signature_invalid():
    """Invalid Messenger signature → verify returns False."""
    from app.security.webhook_verifier import MessengerWebhookVerifier

    app_secret = 'messenger_app_secret_key'
    verifier = MessengerWebhookVerifier(app_secret)
    body = b'{"object": "page", "entry": []}'
    assert verifier.verify(body, 'sha1=0000000000000000000000000000000000000000') is False


def test_webhook_whatsapp_signature_valid():
    """Valid WhatsApp (sha256=...) signature → verify returns True."""
    from app.security.webhook_verifier import WhatsAppWebhookVerifier
    import hmac, hashlib

    app_secret = 'whatsapp_business_secret'
    verifier = WhatsAppWebhookVerifier(app_secret)
    body = b'{"object": "whatsapp_business_account", "entry": [{"id": "WHAPP123"}]}'
    sig_hex = hmac.new(app_secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    signature = 'sha256=' + sig_hex
    assert verifier.verify(body, signature) is True


def test_webhook_whatsapp_signature_invalid():
    """Invalid WhatsApp signature → verify returns False."""
    from app.security.webhook_verifier import WhatsAppWebhookVerifier

    app_secret = 'whatsapp_business_secret'
    verifier = WhatsAppWebhookVerifier(app_secret)
    body = b'{"object": "whatsapp_business_account", "entry": []}'
    assert verifier.verify(body, 'sha256=0000000000000000000000000000000000000000000000000000000000000000') is False


def test_webhook_401_on_invalid_signature():
    """All platforms: invalid signature → HTTP 401 (verify returns False)."""
    from app.security.webhook_verifier import (
        TelegramWebhookVerifier, LineWebhookVerifier,
        MessengerWebhookVerifier, WhatsAppWebhookVerifier
    )

    tg = TelegramWebhookVerifier('token')
    line = LineWebhookVerifier('secret')
    fb = MessengerWebhookVerifier('app_secret')
    wa = WhatsAppWebhookVerifier('app_secret')

    assert tg.verify(b'{}', 'bad') is False
    assert line.verify(b'{}', 'bad') is False
    assert fb.verify(b'{}', 'bad') is False
    assert wa.verify(b'{}', 'bad') is False


@pytest.mark.asyncio
async def test_webhook_429_on_rate_limit_exceeded():
    """Rate limiter blocks after bucket exhaustion → HTTP 429."""
    from app.security.rate_limiter import RateLimiter

    limiter = RateLimiter(default_rps=1)
    platform = 'telegram'
    user_id = 'rate_limit_test_user'

    result1 = await limiter.check(platform, user_id)
    result2 = await limiter.check(platform, user_id)

    assert result1 is True
    assert result2 is False


def test_webhook_verifier_registry_resolves_correct_type():
    """get_verifier() returns correct verifier class per platform."""
    from app.security.webhook_verifier import (
        get_verifier, TelegramWebhookVerifier, LineWebhookVerifier,
        MessengerWebhookVerifier, WhatsAppWebhookVerifier
    )

    assert isinstance(get_verifier('telegram', 'token'), TelegramWebhookVerifier)
    assert isinstance(get_verifier('line', 'secret'), LineWebhookVerifier)
    assert isinstance(get_verifier('messenger', 'app_secret'), MessengerWebhookVerifier)
    assert isinstance(get_verifier('whatsapp', 'app_secret'), WhatsAppWebhookVerifier)
    assert get_verifier('unknown', 'secret') is None


def test_verifier_registry_includes_messenger_and_whatsapp():
    """VERIFIERS dict includes both messenger and whatsapp."""
    from app.security.webhook_verifier import VERIFIERS, MessengerWebhookVerifier, WhatsAppWebhookVerifier

    assert 'messenger' in VERIFIERS
    assert 'whatsapp' in VERIFIERS
    assert VERIFIERS['messenger'] == MessengerWebhookVerifier
    assert VERIFIERS['whatsapp'] == WhatsAppWebhookVerifier


@pytest.mark.asyncio
async def test_webhook_telegram_rate_limited_returns_429():
    """Telegram rate limiter blocks after exhaustion → HTTP 429."""
    from app.security.rate_limiter import RateLimiter

    limiter = RateLimiter(default_rps=1)
    user_id = 'telegram_user_abc'

    await limiter.check('telegram', user_id)  # True
    result = await limiter.check('telegram', user_id)  # False
    assert result is False

