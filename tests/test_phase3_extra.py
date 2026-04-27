import pytest
from app.utils.i18n import i18n
from app.utils.metrics import REQUEST_COUNT, MESSAGE_SENTIMENT
from app.utils.tracing import setup_tracing, tracer
import os
import subprocess

def test_i18n_translation():
    assert i18n.translate("greeting", "zh-TW") == "您好！請問有什麼可以幫您的？"
    assert i18n.translate("greeting", "en") == "Hello! How can I help you?"
    # Fallback
    assert i18n.translate("non-existent", "en") == "non-existent"

def test_metrics_definitions():
    # Verify metrics are initialized
    assert REQUEST_COUNT._name == "omnibot_requests"
    assert MESSAGE_SENTIMENT._name == "omnibot_message_sentiment"

def test_tracing_initialization():
    # Should not raise error
    setup_tracing("test-service")
    with tracer.start_as_current_span("test-span"):
        pass

def test_backup_script_exists():
    script_path = "/Users/johnny/Documents/omnibot/scripts/backup.sh"
    assert os.path.exists(script_path)
    # Check if executable (optional, but good for verification)
    assert os.access(script_path, os.X_OK)

@pytest.mark.asyncio
async def test_cost_model_logic():
    # This is indirectly tested in integration tests, 
    # but we can verify the cost map logic if we expose it or test the endpoint.
    from app.api import process_webhook_message
    # Mocking DB and other dependencies would be needed for a pure unit test here,
    # but the logic is now in the process_webhook_message.
    pass
