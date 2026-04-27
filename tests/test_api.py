import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from app.api import app
from app.models.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result
    db.add = MagicMock()
    return db

@pytest.fixture
def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)

def test_health_check_healthy(client, mock_db):
    # Setup mock for successful DB check
    mock_db.execute.return_value = MagicMock()
    
    with patch("redis.asyncio.from_url") as mock_redis_from_url:
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["postgres"] is True
        assert data["redis"] is True

def test_health_check_degraded(client, mock_db):
    # Mock DB failure
    mock_db.execute.side_effect = Exception("DB Down")
    
    with patch("redis.asyncio.from_url") as mock_redis_from_url:
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Redis Down")
        mock_redis_from_url.return_value = mock_redis
        
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["postgres"] is False
        assert data["redis"] is False

def test_rate_limit_429(client):
    with patch("app.security.RateLimiter.check", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = False
        
        response = client.post("/api/v1/webhook/telegram", json={"message": {"text": "hi", "from": {"id": 1}}})
        assert response.status_code == 429
        assert "請求頻率過高" in response.json()["detail"]

@patch("app.api.process_webhook_message", new_callable=AsyncMock)
@patch("app.api.get_or_create_user", new_callable=AsyncMock)
@patch("app.api.get_active_conversation", new_callable=AsyncMock)
def test_telegram_webhook_normal(mock_get_conv, mock_get_user, mock_process, client):
    mock_process.return_value = ("這是為您生成的個人化回覆", "llm")
    
    payload = {
        "message": {
            "from": {"id": 12345},
            "text": "你好，我想詢問課程資訊"
        }
    }
    response = client.post("/api/v1/webhook/telegram", json=payload)
    assert response.status_code == 200
    assert "這是為您生成的個人化回覆" in response.json()["data"]["response"]

def test_knowledge_crud_rbac(client):
    # admin can do everything
    headers = {"X-User-Role": "admin"}
    
    # Create
    response = client.post("/api/v1/knowledge", json={"q": "new", "a": "ans"}, headers=headers)
    assert response.status_code == 200
    
    # Update
    response = client.put("/api/v1/knowledge/1", json={"a": "updated"}, headers=headers)
    assert response.status_code == 200
    
    # Delete
    response = client.delete("/api/v1/knowledge/1", headers=headers)
    assert response.status_code == 200
    
    # Bulk
    response = client.post("/api/v1/knowledge/bulk", json={"items": [{"q": "1"}]}, headers=headers)
    assert response.status_code == 200

def test_knowledge_crud_forbidden(client):
    # agent can only read knowledge
    headers = {"X-User-Role": "agent"}
    
    response = client.post("/api/v1/knowledge", json={}, headers=headers)
    assert response.status_code == 403
    
    response = client.delete("/api/v1/knowledge/1", headers=headers)
    assert response.status_code == 403

def test_conversations_list_rbac(client):
    response = client.get("/api/v1/conversations", headers={"X-User-Role": "admin"})
    assert response.status_code == 200
    
    response = client.get("/api/v1/conversations", headers={"X-User-Role": "agent"})
    assert response.status_code == 200 # Agents can read conversations
    
    response = client.get("/api/v1/conversations", headers={"X-User-Role": "unknown"})
    assert response.status_code == 403
