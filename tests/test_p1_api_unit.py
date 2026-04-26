import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from app.api import app, get_db
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

client = TestClient(app)

# Mock DB dependency
@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    # Configure execute to return a mock result that supports scalars().all()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.fetchall.return_value = []
    db.execute.return_value = mock_result
    return db

@pytest.fixture
def override_get_db(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.pop(get_db, None)

# 2.3 API 端點驗證 - Health Check
class TestHealthApi:
    @patch("redis.asyncio.from_url")
    def test_health_check_success(self, mock_redis_from_url, override_get_db, mock_db):
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["postgres"] is True
        assert data["redis"] is True

# 2.3 API 端點驗證 - Webhooks
class TestWebhookApi:
    @patch("app.api.verify_signature")
    def test_telegram_webhook_invalid_signature(self, mock_verify, override_get_db, mock_db):
        mock_verify.return_value = False
        
        response = client.post(
            "/api/v1/webhook/telegram",
            json={"message": {"text": "hello"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}
        )
        assert response.status_code == 401
        assert response.json()["error_code"] == "AUTH_INVALID_SIGNATURE"

    @patch("app.api.verify_signature")
    @patch("app.api.get_or_create_user", new_callable=AsyncMock)
    @patch("app.api.get_active_conversation", new_callable=AsyncMock)
    @patch("app.services.knowledge.HybridKnowledgeV7.query", new_callable=AsyncMock)
    def test_telegram_webhook_success(self, mock_query, mock_get_conv, mock_get_user, mock_verify, override_get_db, mock_db):
        mock_verify.return_value = True
        
        # Mock User
        mock_user = MagicMock()
        mock_user.platform = "telegram"
        mock_user.platform_user_id = "123"
        mock_user.unified_user_id = "uuid-123"
        mock_get_user.return_value = mock_user
        
        # Mock Conversation
        mock_conv = MagicMock()
        mock_conv.id = 1
        mock_get_conv.return_value = mock_conv
        
        # Mock Knowledge Result
        from app.models import KnowledgeResult
        mock_query.return_value = KnowledgeResult(id=1, content="Reply", confidence=0.95, source="rule")
        
        response = client.post(
            "/api/v1/webhook/telegram",
            json={"message": {"from": {"id": "123"}, "text": "hello"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
