import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from app.api import app
from app.models.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

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
def override_get_db(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture
def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)

def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "postgres" in data
    assert "redis" in data
    assert "uptime_seconds" in data

@patch("app.api.get_or_create_user", new_callable=AsyncMock)
@patch("app.api.get_active_conversation", new_callable=AsyncMock)
def test_telegram_webhook_pii(mock_get_conv, mock_get_user, client):
    mock_user = MagicMock()
    mock_user.platform = "telegram"
    mock_user.platform_user_id = "12345"
    mock_user.unified_user_id = "uuid-1"
    mock_get_user.return_value = mock_user

    mock_conv = MagicMock()
    mock_conv.id = 1
    mock_get_conv.return_value = mock_conv

    payload = {
        "message": {
            "from": {"id": 12345},
            "text": "我的電話是 0912345678，請幫我修改密碼"
        }
    }
    response = client.post("/api/v1/webhook/telegram", json=payload)
    assert response.status_code == 200
    assert "正在為您轉接人工客服" in response.json()["data"]["response"]

@patch("app.api.get_or_create_user", new_callable=AsyncMock)
@patch("app.api.get_active_conversation", new_callable=AsyncMock)
def test_telegram_webhook_normal(mock_get_conv, mock_get_user, client):
    mock_user = MagicMock()
    mock_user.platform = "telegram"
    mock_user.platform_user_id = "12345"
    mock_user.unified_user_id = "uuid-1"
    mock_get_user.return_value = mock_user

    mock_conv = MagicMock()
    mock_conv.id = 1
    mock_get_conv.return_value = mock_conv

    payload = {
        "message": {
            "from": {"id": 12345},
            "text": "你好，我想詢問課程資訊"
        }
    }
    response = client.post("/api/v1/webhook/telegram", json=payload)
    assert response.status_code == 200
    assert "正在為您轉接人工客服" in response.json()["data"]["response"]

@patch("app.api.get_or_create_user", new_callable=AsyncMock)
@patch("app.api.get_active_conversation", new_callable=AsyncMock)
def test_line_webhook(mock_get_conv, mock_get_user, client):
    mock_user = MagicMock()
    mock_user.platform = "line"
    mock_user.platform_user_id = "user-line-1"
    mock_user.unified_user_id = "uuid-2"
    mock_get_user.return_value = mock_user

    mock_conv = MagicMock()
    mock_conv.id = 2
    mock_get_conv.return_value = mock_conv

    payload = {
        "events": [
            {
                "type": "message",
                "message": {"text": "Hello LINE"}
            }
        ]
    }
    response = client.post("/api/v1/webhook/line", json=payload)
    assert response.status_code == 200
    assert len(response.json()["data"]["responses"]) == 1

def test_knowledge_query(client):
    response = client.get("/api/v1/knowledge?q=test")
    assert response.status_code == 200
    assert "items" in response.json()["data"]
