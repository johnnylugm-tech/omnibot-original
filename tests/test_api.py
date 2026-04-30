from app.security.rbac import rbac
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
    
    def side_effect_add(obj):
        if hasattr(obj, 'id') and obj.id is None:
            obj.id = 1
            
    db.add = MagicMock(side_effect=side_effect_add)
    # Mock scalar_one_or_none to return the object for the update/delete tests
    def set_scalar_return(obj):
        db.execute.return_value.scalar_one_or_none.return_value = obj
        
    db.set_scalar_return = set_scalar_return
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

def test_health_check_status_unhealthy_when_service_down(client, mock_db):
    """When both Postgres and Redis are down, health returns status=degraded (not healthy)."""
    # Both DB and Redis are unavailable (use a message that won't re-raise)
    mock_db.execute.side_effect = Exception("Connection refused")
    
    with patch("redis.asyncio.from_url") as mock_redis_from_url:
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Redis connection refused")
        mock_redis_from_url.return_value = mock_redis
        
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["postgres"] is False
        assert data["redis"] is False

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

def test_llm_timeout_504(client):
    with patch("app.api.process_webhook_message", new_callable=AsyncMock) as mock_process:
        mock_process.side_effect = TimeoutError("LLM request timed out")
        
        payload = {"message": {"from": {"id": 1}, "text": "hi"}}
        response = client.post("/api/v1/webhook/telegram", json=payload)
        
        assert response.status_code == 504
        assert response.json()["detail"] == "LLM_TIMEOUT"

def test_knowledge_crud_rbac(client, mock_db):
    # admin can do everything
    headers = {"Authorization": f"Bearer {rbac.create_token('admin')}"}
    
    # Create
    response = client.post("/api/v1/knowledge", json={"question": "new", "answer": "ans"}, headers=headers)
    assert response.status_code == 200
    kid = response.json()["data"]["id"]
    
    # Mock for Update/Delete
    from app.models.database import KnowledgeBase
    mock_k = KnowledgeBase(id=kid, question="new", answer="ans", is_active=True, version=1)
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_k
    
    # Update
    response = client.put(f"/api/v1/knowledge/{kid}", json={"answer": "updated"}, headers=headers)
    if response.status_code == 422:
        print(response.json())
    assert response.status_code == 200
    
    # Delete
    response = client.delete(f"/api/v1/knowledge/{kid}", headers=headers)
    assert response.status_code == 200
    
    # Bulk
    response = client.post("/api/v1/knowledge/bulk", json={"items": [{"question": "1", "answer": "1"}]}, headers=headers)
    assert response.status_code == 200

def test_knowledge_crud_forbidden(client):
    # agent can only read knowledge
    headers = {"Authorization": f"Bearer {rbac.create_token('agent')}"}
    
    response = client.post("/api/v1/knowledge", json={}, headers=headers)
    assert response.status_code == 403
    
    response = client.delete("/api/v1/knowledge/1", headers=headers)
    assert response.status_code == 403

def test_conversations_list_rbac(client):
    response = client.get("/api/v1/conversations", headers={"Authorization": "Bearer eyJyb2xlIjogImFkbWluIn0.78f2e30e15e2d24f56e94b18a4b8fb611313993b48a78d4bca5895c6764f1f5a"})
    assert response.status_code == 200
    
    response = client.get("/api/v1/conversations", headers={"Authorization": "Bearer eyJyb2xlIjogImFnZW50In0.c7885d0c7f0dfc6b944c9633ebd12c237c609258bd643938e9366204c6c95dc6"})
    assert response.status_code == 200 # Agents can read conversations
    
    response = client.get("/api/v1/conversations", headers={"Authorization": "Bearer eyJyb2xlIjogInVua25vd24ifQ.ee34e1fe9156751d5f00c5fd77bf11ff4e48a4e6e1d5d017b230d82f820cd0c4"})
    assert response.status_code == 403
