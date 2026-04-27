from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.api import app
from app.models.database import get_db

# Mock DB dependency
mock_db = AsyncMock()
mock_db.add = MagicMock() # SQLAlchemy add is sync
app.dependency_overrides[get_db] = lambda: mock_db

client = TestClient(app)

def test_health_check():
    # Setup mock for DB check
    mock_db.execute.return_value = MagicMock()
    
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "postgres" in data
    assert "redis" in data
    assert "uptime_seconds" in data

def test_telegram_webhook_pii():
    # 測試包含 PII 的訊息是否會觸發遮罩與轉接人工
    payload = {
        "message": {
            "from": {"id": 12345},
            "text": "我的電話是 0912345678，請幫我修改密碼"
        }
    }
    response = client.post("/api/v1/webhook/telegram", json=payload)
    assert response.status_code == 200
    assert "正在為您轉接人工客服" in response.json()["data"]["response"]

def test_telegram_webhook_normal():
    payload = {
        "message": {
            "from": {"id": 12345},
            "text": "你好，我想詢問課程資訊"
        }
    }
    response = client.post("/api/v1/webhook/telegram", json=payload)
    assert response.status_code == 200
    # Phase 3 修復：現在會回傳 AI 生成的回覆（Layer 3），而非直接轉接人工
    assert "這是為您生成的個人化回覆" in response.json()["data"]["response"]

def test_line_webhook():
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

def test_knowledge_query():
    # 需要提供 RBAC 角色頭部
    response = client.get("/api/v1/knowledge?q=test", headers={"X-User-Role": "admin"})
    assert response.status_code == 200
    assert "items" in response.json()["data"]

def test_conversations_list_rbac():
    # 測試 RBAC 是否生效於 Conversations 列表
    response = client.get("/api/v1/conversations", headers={"X-User-Role": "admin"})
    assert response.status_code == 200
    
    # 測試無權限角色
    response = client.get("/api/v1/conversations", headers={"X-User-Role": "agent"})
    assert response.status_code == 403
