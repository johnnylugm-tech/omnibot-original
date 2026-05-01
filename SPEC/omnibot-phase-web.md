# OmniBot Phase Web: Web 入口 — 即時聊天 + 自助服務

---

## 專案概述

| 項目 | 內容 |
|--------|------|
| **專案名稱** | OmniBot - 多平台客服機器人 |
| **階段** | Phase Web（Web 入口） |
| **目標** | 支援瀏覽器即時聊天 + 自助服務，覆蓋不使用社群平台的用戶 |
| **核心原則** | 復用既有處理管線、新增 Web 專屬認證與即時通訊層 |
| **開發時間** | 3-4 週 |
| **前置條件** | Phase 1 + Phase 2 完成（Phase 3 可選） |

### 與既有 Phase 的關係

Phase Web **依賴** Phase 1 + Phase 2 的核心處理管線：
- UnifiedMessage / UnifiedResponse 格式
- HybridKnowledgeLayer（Layer 1-4）
- InputSanitizer、PII Masking、Emotion Analyzer、DST
- conversations / messages 資料庫 Schema

Phase Web **不依賴** Phase 3（RBAC/A/B/災備），但部署時 Phase 3 的監控與災備機制可同時啟用。

---

## 商業目標

| KPI | Phase Web 目標 | 實現路徑 |
|-----|---------------|----------|
| **Web FCR** | >= 75% | 復用 Layer 1-4，既有高 FCR 基礎 |
| **Web 滲透率** | 對話量中 Web 佔比 20-30% | 降低進入門檻，無需安裝 App |
| **p95 回應延遲（WebSocket）** | < 1.5s | WebSocket 消除 HTTP polling 延遲 |
| **Session 留存** | 30 天有效登入 Session | JWT refresh token 機制 |
| **可用性** | 99.9%（復用 Phase 3 基礎） | 水準擴展 + Redis Pub/Sub |

---

## 系統架構 Phase Web

### 完整架構圖

```
+---------------------------------------------------------------------+
|                    OmniBot Phase Web 完整架構                         |
+---------------------------------------------------------------------+

  +------------------------------------------------------------+
  |                     Web Browser (Client)                     |
  |                   Chat UI / Web Application                   |
  +-------------------------------+--------------------------------+
                                  |  WebSocket (wss://) / HTTP REST
  +------------------------------------------------------------+
  |                  API Gateway (Phase 1 基礎)                   |
  |   - Rate Limiting (Token Bucket) ← Phase 1                  |
  |   - TLS 終結 ← Phase 1                                      |
  |   - IP Whitelist ← Phase 3                                  |
  |   - CORS Configuration ← Phase Web NEW                       |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |           WebAuthMiddleware ← Phase Web NEW                  |
  |         JWT / Session 驗證（取代 Webhook 簽名驗證）            |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |           WebSocket Handler ← Phase Web NEW                   |
  |         即時雙向訊息 / 連線狀態管理 / 斷線重連                |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              Platform Adapter Layer ← Phase 1+2              |
  |         + WebPlatformAdapter ← Phase Web NEW                  |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              Input Sanitizer L2 ← Phase 1                    |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              Prompt Injection Defense L3 ← Phase 2           |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              PII Masking L4 ← Phase 2                       |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              Emotion Analyzer ← Phase 2                      |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              Intent Router + DST ← Phase 2                   |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              Hybrid Knowledge Layer ← Phase 2                 |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              Grounding Checks L5 ← Phase 2                  |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              Response Generator                              |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |         Redis Pub/Sub (WebSocket 跨實例廣播) ← Phase Web NEW |
  +------------------------------------------------------------+
                                  |
  +------------------------------------------------------------+
  |              Observability Layer                              |
  |         Prometheus + Grafana + OpenTelemetry ← Phase 3       |
  +------------------------------------------------------------+
```

### Web 請求流向（與 Webhook 流向對比）

| 步驟 | Webhook 流向（既有） | Web 流向（Phase Web） |
|------|---------------------|----------------------|
| 1 | 第三方平台 Server 推送 | 瀏覽器 WebSocket 連線 |
| 2 | WebhookVerifier 驗證簽名 | WebAuthMiddleware 驗證 JWT |
| 3 | PlatformAdapter 轉換訊息 | WebPlatformAdapter 轉換訊息 |
| 4 | 進入 UnifiedMessage 管線 | 進入 UnifiedMessage 管線（相同） |
| 5 | KnowledgeLayer 處理 | KnowledgeLayer 處理（相同） |
| 6 | 回應送回平台 | 回應透過 WebSocket 推送 |
| 7 | — | 對話寫入 conversations/messages |

---

## 平台識別

### Platform Enum 擴展

```python
# Phase 1 既有：
class Platform(Enum):
    TELEGRAM = "telegram"
    LINE = "line"
    MESSENGER = "messenger"
    WHATSAPP = "whatsapp"

# Phase Web 新增：
    WEB = "web"
```

### 斷言：所有既有 Platform 值不變

```
斷言：Platform enum 新增 WEB 後，
既有程式碼中 if platform == Platform.LINE 的所有分支行為不變。
```

---

## Web 認證與會話管理

### 認證模型總覽

```
Phase Web 使用兩種 Token：

1. Access Token（JWT）
   - 有效期間：15 分鐘
   - 攜帶於 WebSocket handshake（query param）或 HTTP Authorization header
   - 包含：user_id, session_id, role, exp

2. Refresh Token
   - 有效期間：30 天
   - 儲存於 httpOnly Cookie（防 XSS）
   - 用於 Access Token 過期時換發
   - 一次一用（rotation on use）

登入流程：
  瀏覽器 ──(email+password)──> POST /api/v1/auth/login
                          <── { access_token, user }

  瀏覽器獲得 access_token 後，連線 WebSocket：
  wss://host/ws/chat?token=<access_token>

  Access Token 過期時（收到 4401）：
  瀏覽器 ──(refresh_token in cookie)──> POST /api/v1/auth/refresh
                                   <── { access_token }
```

### WebAuthMiddleware

```python
# app/web/auth.py
import jwt
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

@dataclass(frozen=True)
class WebUser:
    """Web 登入用戶（區別於 platform webhook 用戶）"""
    user_id: str          # UUID，關聯 users.unified_user_id
    session_id: str       # 會話 ID
    role: str             # web_user | web_agent | admin
    email: Optional[str] = None
    oauth_provider: Optional[str] = None  # google | github | None

class TokenManager:
    """JWT Access Token + Refresh Token 管理"""

    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 15
    REFRESH_TOKEN_EXPIRE_DAYS = 30

    def __init__(self, secret_key: str):
        self._secret = secret_key

    def create_access_token(
        self,
        user_id: str,
        session_id: str,
        role: str = "web_user",
    ) -> str:
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "sid": session_id,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._secret, algorithm=self.ALGORITHM)

    def create_refresh_token(self, user_id: str, session_id: str) -> str:
        now = datetime.utcnow()
        # Refresh token 使用不同的聲明結構
        payload = {
            "sub": user_id,
            "sid": session_id,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            "jti": str(uuid.uuid4()),
            # 用於旋轉校驗：hash(access_token_jti + refresh_token_jti)
        }
        return jwt.encode(payload, self._secret, algorithm=self.ALGORITHM)

    def verify_access_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=[self.ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=4401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=4401, detail="Invalid token")

        if payload.get("type") != "access":
            raise HTTPException(status_code=4401, detail="Not an access token")
        return payload

    def verify_refresh_token(self, token: str) -> dict:
        payload = jwt.decode(
            token, self._secret, algorithms=[self.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=4401, detail="Not a refresh token")
        return payload

    def get_user_from_payload(self, payload: dict) -> WebUser:
        return WebUser(
            user_id=payload["sub"],
            session_id=payload["sid"],
            role=payload.get("role", "web_user"),
        )


class WebAuthMiddleware:
    """
    FastAPI 中介程式：驗證 JWT Access Token。

    掛載點：所有 /api/v1/web/* 端點。
    WebSocket 握手時透過 query param ?token=<access_token> 傳遞。
    HTTP 端點透過 Authorization: Bearer <access_token> 傳遞。

    Phase 3 RBAC BearerToken 專門保護管理 API（/api/v1/knowledge 等），
    與本中介程式服務的目標端點不同，兩者不衝突。
    """

    def __init__(
        self,
        token_manager: TokenManager,
        get_db,
    ):
        self._token = token_manager
        self._get_db = get_db

    async def __call__(self, request: Request, call_next):
        # 排除公開端點（不需認證）
        public_paths = {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/verify-email",
            "/ws/chat",            # WebSocket，單獨處理
            "/api/v1/health",
        }
        if request.url.path in public_paths:
            return await call_next(request)

        # 從 header 或 query 提取 token
        token = self._extract_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="Missing token")

        # 驗證並取得用戶
        payload = self._token.verify_access_token(token)
        user = self._token.get_user_from_payload(payload)

        # Session 有效性檢查（Redis 中查詢是否未撤銷）
        db = self._get_db()
        session = db.get_web_session(user.session_id)
        if session is None or session["revoked_at"] is not None:
            raise HTTPException(status_code=401, detail="Session revoked")

        # 附加到 request state
        request.state.web_user = user
        return await call_next(request)

    def _extract_token(self, request: Request) -> Optional[str]:
        # Header: Authorization: Bearer <token>
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]

        # Query: ?token=<token>（WebSocket 握手時使用）
        return request.query_params.get("token")
```

### 密碼雜湊

```python
# app/web/passwords.py
import argon2
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=3,        # 3 次疊代
    memory_cost=65536, # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

def hash_password(password: str) -> str:
    """argon2id 雜湊（抵禦 GPU 暴力破解）"""
    return ph.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """驗證密碼，回傳 True/False（不定時攻擊安全）"""
    try:
        return ph.verify(hashed, password)
    except argon2.exceptions.VerifyMismatchError:
        return False
```

### 登入端點

```python
# app/api/web/auth.py
from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel, EmailStr
from app.web.auth import TokenManager, WebUser, hash_password, verify_password
from app.web.sessions import WebSessionManager

router = APIRouter(prefix="/api/v1/auth", tags=["web-auth"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str          # 明文，前端需滿足複雜度要求

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int         # access_token 有效秒數

class UserResponse(BaseModel):
    user_id: str
    email: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    tm: TokenManager,
    sm: WebSessionManager,
    db,
):
    """Web 登入：驗證帳密、發放 tokens、設定 httpOnly cookie"""

    user = db.get_web_user_by_email(body.email)
    if user is None or not verify_password(body.password, user["password_hash"]):
        # 為防止使用者枚舉攻擊，無論是否存在皆回相同錯誤
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_id = str(uuid.uuid4())
    access_token = tm.create_access_token(user["user_id"], session_id, user["role"])
    refresh_token = tm.create_refresh_token(user["user_id"], session_id)

    # 寫入 web_sessions 表
    sm.create(
        session_id=session_id,
        user_id=user["user_id"],
        refresh_token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
        user_agent=None,  # 從 request 提取
        ip_address=None,   # 從 request 提取
    )

    # Refresh token 寫入 httpOnly Cookie（防 XSS）
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,       # HTTPS only
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=tm.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register")
async def register(body: RegisterRequest, db):
    """Web 註冊：新用戶寫入 users 表（platform='web'）"""
    existing = db.get_web_user_by_email(body.email)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = str(uuid.uuid4())
    password_hash = hash_password(body.password)

    db.create_web_user(
        user_id=user_id,
        email=body.email,
        password_hash=password_hash,
        role="web_user",
    )

    return {"user_id": user_id, "email": body.email}


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    tm: TokenManager,
    sm: WebSessionManager,
    db,
):
    """Refresh Token 換發 Access Token（一次性旋轉）"""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = tm.verify_refresh_token(refresh_token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Refresh token rotation 校驗：確認未被使用過（盜用偵測）
    session = sm.get_by_token_hash(
        hashlib.sha256(refresh_token.encode()).hexdigest()
    )
    if session is None or session["revoked_at"] is not None:
        # Token 已被使用過：可能遭盜用，全數撤銷該 session
        if session:
            sm.revoke_all_user_sessions(session["user_id"])
        raise HTTPException(status_code=401, detail="Token reuse detected")

    # 旋轉：撤銷舊 refresh token，發放新的
    sm.revoke(session["session_id"])

    new_session_id = str(uuid.uuid4())
    new_access_token = tm.create_access_token(
        payload["sub"], new_session_id, role=payload.get("role", "web_user")
    )
    new_refresh_token = tm.create_refresh_token(payload["sub"], new_session_id)

    sm.create(
        session_id=new_session_id,
        user_id=payload["sub"],
        refresh_token_hash=hashlib.sha256(new_refresh_token.encode()).hexdigest(),
        user_agent=None,
        ip_address=None,
    )

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )

    return {
        "access_token": new_access_token,
        "expires_in": tm.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout")
async def logout(
    request: Request,
    web_user: WebUser = Depends(get_web_user),
    sm: WebSessionManager,
):
    """登出：撤銷目前 session"""
    sm.revoke(web_user.session_id)
    return {"success": True}
```

---

## WebSocket 即時通訊

### WebSocket 端點

```
/ws/chat
  Protocol: WebSocket (wss:// in production)
  Auth: ?token=<access_token> in handshake URL
  Messages: JSON (text only, binary not supported)
```

### 連線流程

```
1. 瀏覽器 GET /ws/chat?token=<access_token>&client_id=<uuid>
   （WebSocket 握手，token 在 query string）

2. 伺服器驗證 token：
   - token 有效 → 接受連線，發送 { type: "connected", session_id, server_time }
   - token 無效/過期 → 發送 { type: "auth_failed", code: 4401 }，關閉連線

3. 連線建立後，瀏覽器與伺服器雙向傳送訊息
```

### WebSocket 訊息格式（客戶端 → 伺服器）

```python
# app/web/websocket/messages.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import uuid

class WSMessageType(Enum):
    # 客戶端 → 伺服器
    SEND_MESSAGE = "send_message"
    TYPING_START = "typing_start"
    TYPING_END = "typing_end"
    GET_HISTORY = "get_history"
    FEEDBACK = "feedback"
    PING = "ping"

    # 伺服器 → 客戶端
    MESSAGE = "message"           # 機器人回覆
    TYPING_INDICATOR = "typing"  # 打字中提示
    MESSAGE_ACK = "message_ack"   # 訊息已收到確認
    ERROR = "error"
    PONG = "pong"
    HISTORY = "history"            # 對話歷史回覆

@dataclass(frozen=True)
class WSIncomingMessage:
    """客戶端發送的 WebSocket 訊息（輸入）"""
    mid: str = field(default_factory=lambda: str(uuid.uuid4()))  # 客戶端訊息 ID
    type: WSMessageType
    payload: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_unified(self, user: WebUser) -> "UnifiedMessage":
        """轉換為 UnifiedMessage 格式"""
        return UnifiedMessage(
            platform=Platform.WEB,
            platform_user_id=user.user_id,
            unified_user_id=user.user_id,
            message_type=MessageType.TEXT,
            content=self.payload.get("content", ""),
            raw_payload={
                "ws_mid": self.mid,
                "session_id": user.session_id,
            },
            received_at=self.timestamp,
        )

@dataclass
class WSOutgoingMessage:
    """伺服器發送的 WebSocket 訊息（輸出）"""
    type: WSMessageType
    payload: dict
    server_time: str = field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    sid: str = ""  # server-assigned message ID

    def to_json(self) -> str:
        import json
        data = {
            "type": self.type.value,
            "payload": self.payload,
            "server_time": self.server_time,
            "sid": self.sid,
        }
        return json.dumps(data)
```

### 訊息樣式

**客戶端 → 伺服器（SEND_MESSAGE）：**
```json
{
  "type": "send_message",
  "mid": "client-msg-uuid-001",
  "payload": {
    "content": "我想查詢退貨政策"
  }
}
```

**伺服器 → 客戶端（MESSAGE）：**
```json
{
  "type": "message",
  "sid": "server-msg-uuid-001",
  "server_time": "2026-05-01T12:00:00.123Z",
  "payload": {
    "content": "退貨政策如下...",
    "source": "rule",
    "confidence": 0.95,
    "knowledge_id": 42
  }
}
```

**打字中提示（伺服器 → 客戶端）：**
```json
{
  "type": "typing",
  "sid": "",
  "server_time": "2026-05-01T12:00:00.050Z",
  "payload": {}
}
```

### WebSocket Handler

```python
# app/web/websocket/handler.py
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from app.web.websocket.messages import (
    WSMessageType, WSIncomingMessage, WSOutgoingMessage,
)
from app.web.auth import TokenManager, WebUser

logger = logging.getLogger("omnibot.websocket")

class WebSocketConnectionManager:
    """
    管理所有 WebSocket 連線。

    水準擴展：所有實例共享同一個 Redis Pub/Sub channel。
    每個 session_id 對應一個 WebSocket 連線（單一瀏覽分頁）。
    """

    def __init__(self, redis):
        self._redis = redis
        self._connections: dict[str, WebSocket] = {}  # session_id → WebSocket
        self._pubsub = None

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id] = websocket
        # 訂閱該 session 的 Redis channel（跨實例訊息廣播）
        await self._redis.subscribe(f"ws:session:{session_id}")

    async def disconnect(self, session_id: str) -> None:
        ws = self._connections.pop(session_id, None)
        if ws:
            try:
                await ws.close()
            except Exception:
                pass
        await self._redis.unsubscribe(f"ws:session:{session_id}")

    async def send_to_session(self, session_id: str, message: WSOutgoingMessage) -> None:
        """透過 Redis Pub/Sub 廣播至所有持有該 session 的實例"""
        await self._redis.publish(
            f"ws:session:{session_id}",
            json.dumps({
                "type": message.type.value,
                "payload": message.payload,
                "server_time": message.server_time,
                "sid": message.sid,
            })
        )

    async def broadcast(self, message: dict) -> None:
        """系統廣播（例如：維護通知）"""
        for ws in self._connections.values():
            try:
                await ws.send_json(message)
            except Exception:
                pass

    @property
    def connection_count(self) -> int:
        return len(self._connections)


class WebSocketHandler:
    """
    WebSocket 連線生命週期管理。

    Phase 3 Redis Streams 用於 async 訊息處理（AsyncMessageProcessor），
    本模組使用 Redis Pub/Sub 專門服務 WebSocket 即時廣播，兩者不衝突。
    """

    def __init__(
        self,
        manager: WebSocketConnectionManager,
        token_manager: TokenManager,
        knowledge_layer,    # HybridKnowledgeLayer 實例
        escalation_manager,
        intent_router,
        emotion_analyzer,
    ):
        self._mgr = manager
        self._token = token_manager
        self._knowledge = knowledge_layer
        self._escalation = escalation_manager
        self._intent = intent_router
        self._emotion = emotion_analyzer

    async def handle(self, websocket: WebSocket, token: str) -> None:
        """處理一個 WebSocket 連線"""
        # 1. 驗證 token
        try:
            payload = self._token.verify_access_token(token)
            user = self._token.get_user_from_payload(payload)
        except Exception as e:
            await websocket.send_json({
                "type": "auth_failed",
                "code": 4401,
                "detail": str(e),
            })
            await websocket.close(code=4401)
            return

        session_id = user.session_id
        await self._mgr.connect(session_id, websocket)

        # 2. 發送連線確認
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "server_time": datetime.utcnow().isoformat() + "Z",
        })

        # 3. 進入訊息處理循環
        try:
            while True:
                raw = await websocket.receive_text()
                await self._on_message(user, raw)
        except WebSocketDisconnect:
            logger.info("websocket_disconnect", session_id=session_id)
        except Exception as e:
            logger.error("websocket_error", session_id=session_id, error=str(e))
        finally:
            await self._mgr.disconnect(session_id)

    async def _on_message(self, user: WebUser, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(user.session_id, "Invalid JSON")
            return

        msg_type = data.get("type")
        msg_id = data.get("mid", "")

        # 簡單路由
        handlers = {
            WSMessageType.SEND_MESSAGE.value: self._handle_send_message,
            WSMessageType.TYPING_START.value: self._handle_noop,
            WSMessageType.TYPING_END.value: self._handle_noop,
            WSMessageType.GET_HISTORY.value: self._handle_get_history,
            WSMessageType.FEEDBACK.value: self._handle_feedback,
            WSMessageType.PING.value: self._handle_ping,
        }

        handler = handlers.get(msg_type)
        if handler is None:
            await self._send_error(user.session_id, f"Unknown type: {msg_type}")
            return

        incoming = WSIncomingMessage(
            mid=msg_id,
            type=WSMessageType(msg_type),
            payload=data.get("payload", {}),
        )
        await handler(user, incoming)

    async def _handle_send_message(
        self, user: WebUser, incoming: WSIncomingMessage
    ) -> None:
        session_id = user.session_id
        content = incoming.payload.get("content", "").strip()

        if not content:
            return

        # Message ACK：確認收到
        await self._mgr.send_to_session(
            session_id,
            WSOutgoingMessage(
                type=WSMessageType.MESSAGE_ACK,
                payload={"mid": incoming.mid},
                sid=str(uuid.uuid4()),
            )
        )

        # 打字中提示
        await self._mgr.send_to_session(
            session_id,
            WSOutgoingMessage(type=WSMessageType.TYPING_INDICATOR, payload={})
        )

        # 建 UnifiedMessage
        unified = incoming.to_unified(user)

        # 通過既有處理管線（與 webhook 相同）
        response = await self._knowledge.query(
            content, user_context={"user_id": user.user_id}
        )

        # 發送回覆
        server_mid = str(uuid.uuid4())
        await self._mgr.send_to_session(
            session_id,
            WSOutgoingMessage(
                type=WSMessageType.MESSAGE,
                payload={
                    "content": response.content,
                    "source": response.source,
                    "confidence": response.confidence,
                    "knowledge_id": response.knowledge_id,
                    "in_reply_to_mid": incoming.mid,
                },
                sid=server_mid,
            )
        )

        # 寫入 conversations/messages
        self._save_message(user, incoming, response, server_mid)

    async def _handle_get_history(
        self, user: WebUser, incoming: WSIncomingMessage
    ) -> None:
        limit = min(incoming.payload.get("limit", 20), 100)
        messages = self._get_history(user, limit)
        await self._mgr.send_to_session(
            user.session_id,
            WSOutgoingMessage(
                type=WSMessageType.HISTORY,
                payload={"messages": messages},
                sid=str(uuid.uuid4()),
            )
        )

    async def _handle_feedback(
        self, user: WebUser, incoming: WSIncomingMessage
    ) -> None:
        # 回饋寫入 user_feedback 表（Phase 1 schema 已有）
        pass

    async def _handle_ping(self, user: WebUser, incoming: WSIncomingMessage) -> None:
        await self._mgr.send_to_session(
            user.session_id,
            WSOutgoingMessage(type=WSMessageType.PONG, payload={})
        )

    async def _handle_noop(self, user: WebUser, incoming: WSIncomingMessage) -> None:
        pass

    async def _send_error(self, session_id: str, detail: str) -> None:
        await self._mgr.send_to_session(
            session_id,
            WSOutgoingMessage(
                type=WSMessageType.ERROR,
                payload={"detail": detail}
            )
        )

    def _save_message(
        self, user: WebUser, incoming: WSIncomingMessage,
        response, server_mid: str
    ) -> None:
        # 寫入 conversations + messages 表（與既有 webhook 相同流程）
        pass
```

### WebSocket 斷線重連策略

```
1. 瀏覽器偵測到 WebSocket close 事件（code != 1000）
2. 等待 1 秒（避免 immediate reconnect storm）
3. 嘗試重新連線，攜帶同一 access_token（若未過期）
4. 若 token 過期（收到 auth_failed），先呼叫 /auth/refresh
   取得新 token 後再重連
5. 重連成功後，發送 get_history 取得漏收的訊息
6. 最大重試次數：5 次，指數退避（1s, 2s, 4s, 8s, 16s）
```

---

## Web Platform Adapter

```python
# app/web/platform.py
from app.platform import PlatformAdapter, UnifiedMessage, Platform, MessageType

class WebPlatformAdapter(PlatformAdapter):
    """
    Phase Web 新增：Web 平台適配器。

    職責：
    - 提取 Web 請求中的用戶上下文（不同於 webhook 的 headers 驗證）
    - 將 UnifiedMessage 轉換為 WebSocket 推送格式
    - 處理 Web 專屬的 metadata（user_agent, browser_info）
    """

    def extract_user_context(self, request) -> dict:
        """從 WebAuthMiddleware 已驗證的 session 中取得用戶上下文"""
        return {
            "platform": Platform.WEB,
            "platform_user_id": request.state.web_user.user_id,
            "session_id": request.state.web_user.session_id,
            "user_agent": request.headers.get("user-agent", ""),
            "ip_address": self._get_client_ip(request),
        }

    def _get_client_ip(self, request) -> str:
        """優先 X-Forwarded-For（反向代理），其次 direct client IP"""
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
        if request.client:
            return request.client.host
        return ""

    def supports_message_type(self, message_type: MessageType) -> bool:
        """Web 支援的訊息類型（比 webhook 少，初期僅支援文字）"""
        return message_type == MessageType.TEXT

    def get_capabilities(self) -> dict:
        return {
            "typing_indicator": True,   # WebSocket 支援即時打字提示
            "read_receipt": False,       # Phase Web 不支援
            "media_upload": False,        # Phase Web-2
            "multi_media": False,         # Phase Web-2
        }
```

---

## 資料庫 Schema Phase Web

### 既有 users 表擴展

```sql
-- users 表（Phase 1）已存在
-- Phase Web 新增：針對 platform='web' 的用戶新增 credential 欄位
-- 注意：Phase 1 Schema 所有欄位皆已存在，Phase Web 不 ALTER TABLE users，
-- 而是透過單獨的 web_credentials 表關聯

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
  ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE,
  ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50),
  ADD COLUMN IF NOT EXISTS oauth_subject VARCHAR(255);
```

### 新增資料表

```sql
-- ============================================================
-- Web 會話管理（Phase Web 新增）
-- ============================================================
CREATE TABLE web_sessions (
    id SERIAL PRIMARY KEY,
    session_id UUID UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(unified_user_id),
    refresh_token_hash VARCHAR(64) NOT NULL,
    user_agent TEXT,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_web_sessions_user ON web_sessions (user_id);
CREATE INDEX idx_web_sessions_session_id ON web_sessions (session_id);
CREATE INDEX idx_web_sessions_revoked ON web_sessions (revoked_at)
    WHERE revoked_at IS NULL;

-- ============================================================
-- Web 對話視圖（Phase Web 新增，隔離 web vs platform 對話）
-- ============================================================
CREATE TABLE web_conversations (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER UNIQUE NOT NULL
        REFERENCES conversations(id) ON DELETE CASCADE,
    -- 同一個 conversations.id，但專屬於 web 的元資料
    browser VARCHAR(100),
    os VARCHAR(50),
    initial_referrer TEXT,
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- OAuth 關聯（Phase Web 新增，Social Login）
-- ============================================================
CREATE TABLE oauth_accounts (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(unified_user_id),
    provider VARCHAR(50) NOT NULL,  -- google | github | line
    provider_user_id VARCHAR(255) NOT NULL,
    access_token_encrypted TEXT,     -- 加密儲存，不長存
    refresh_token_encrypted TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider, provider_user_id)
);

CREATE INDEX idx_oauth_user ON oauth_accounts (user_id);

-- ============================================================
-- JWT 撤銷日誌（Phase Web 新增，refresh token rotation 支援）
-- ============================================================
CREATE TABLE token_revocation_log (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(unified_user_id),
    session_id UUID REFERENCES web_sessions(session_id),
    revoked_at TIMESTAMPTZ DEFAULT NOW(),
    revoke_reason VARCHAR(50),  -- logout | token_reuse | expired | manual
    jti VARCHAR(64)            -- JWT ID (jti claim)
);

CREATE INDEX idx_token_revocation_user ON token_revocation_log (user_id);
```

### Schema 不需要 ALTER 既有用戶表的聲明

```
斷言：Phase Web 的 users 表擴展（password_hash, email 等）
是為了容納 platform='web' 的用戶，不影響既有 platform 用戶的資料。
同一 users 表同時服務 webhook 平台用戶和 web 用戶，
透過 platform 欄位或新增的 web_sessions / oauth_accounts 表隔離。
```

---

## Rate Limiting 調整

### Web 專屬 Rate Limiting

```python
# app/web/rate_limit.py
from app.api import RateLimiter  # Phase 1 既有的 RateLimiter

class WebRateLimiter:
    """
    Web 流量專屬限速。

    與 Phase 1 RateLimiter 的差異：
    - 鍵值使用 user_id（已登入）而非 platform_user_id
    - 限制更嚴格（匿名用戶無法使用 Web 入口）
    - 新增 WebSocket 訊息頻率限制（每秒 N 條）
    """

    # 已登入用戶
    WEB_MESSAGE_RPS = 10       # 每秒最多 10 條訊息
    WEB_SESSION_RPS = 1        # 每分鐘最多建立 3 個 session

    def __init__(self):
        self._message_limiter = TokenBucketRateLimiter(
            capacity=30, refill_rate=10  # 30 tokens, refill 10/s
        )
        self._session_limiter = TokenBucketRateLimiter(
            capacity=3, refill_rate=0.05  # 3 sessions, refill 1 per 20s
        )

    async def check_message(self, user_id: str) -> bool:
        return self._message_limiter.check(f"web_msg:{user_id}")

    async def check_session(self, user_id: str) -> bool:
        return self._session_limiter.check(f"web_sess:{user_id}")
```

---

## 錯誤碼擴展（Phase Web）

| 錯誤碼 | HTTP Status | 說明 |
|--------|-------------|------|
| 既有錯誤碼 | — | Phase 1-3 既有 8 個錯誤碼不變 |
| `AUTH_TOKEN_EXPIRED` | 4401 | JWT Access Token 過期（Web 專用） |
| `AUTH_SESSION_REVOKED` | 4401 | Session 已被撤銷 |
| `AUTH_TOKEN_REUSE` | 4401 | Refresh Token 重複使用（疑似盜用） |
| `RATE_LIMIT_WEB` | 429 | Web 訊息頻率超出限制 |

---

## CORS 配置

```python
# app/web/cors.py
from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://omnibot.example.com",    # 正式網域
            "https://staging.omnibot.example.com",  # 預發布環境
        ],
        allow_credentials=True,          # 允許 cookie 跨域
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        expose_headers=["X-Request-ID"], # 允許前端讀取自訂 header
    )
```

---

## 前端應用（Phase Web MVP）

### MVP 功能範圍

```
Phase Web MVP（本章規格）：
- 即時一對一聊天（單一對話視窗）
- 打字中提示
- 訊息送達確認
- 對話歷史查詢
- 帳號登入/註冊
- Social Login（Google OAuth）

Phase Web Phase 2（未來擴展）：
- 媒體上傳（圖片/檔案）
- 多視窗對話
- 客服 Agent 即時接管
- 預建 Widget（可嵌入外部網站）
```

### Chat UI 元件需求

```
最小可行 Chat UI（Phase Web MVP）需要：
- 登入/註冊表單
- 對話訊息列表（可滾動）
- 輸入框 + 發送按鈕
- 打字中提示
- 連線狀態指示器（已連線/斷線）
- Session 過期提示 + 重新登入

非功能性要求：
- 響應式設計（支援 Mobile Safari / Chrome Android）
- 無障礙（ARIA labels，鍵盤可操作）
- 離線時顯示提示（Service Worker 可選）
```

### 前端技術選型建議

```
Framework: Vanilla JS + lit-html（最小依賴）或 React/Vue（中型團隊）
即時通訊: Native WebSocket API
打包工具: Vite
CDN: 部署至 Cloudflare CDN 或 S3+CloudFront
```

---

## 監控與 Metrics

### Prometheus 新增 Label

```yaml
# Phase 2 既有的 metrics，新增 platform='web' 支援
metrics:
  - name: omnibot_requests_total
    labels: [platform, status]
    # platform now includes: telegram, line, messenger, whatsapp, web

  - name: omnibot_response_duration_seconds
    labels: [platform, knowledge_source]
    # web platform 與其他平台共用量尺

  # WebSocket 專屬 metrics（Phase Web 新增）
  - name: omnibot_websocket_connections_active
    type: gauge
    description: 目前活躍的 WebSocket 連線數

  - name: omnibot_websocket_messages_total
    type: counter
    labels: [direction]  # inbound | outbound

  - name: omnibot_websocket_disconnect_total
    type: counter
    labels: [reason]  # client_close | server_close | auth_failed | timeout

  - name: omnibot_auth_failures_total
    type: counter
    labels: [reason]  # invalid_token | expired_token | session_revoked | token_reuse
```

### Grafana Dashboard 新增

```
Panel: WebSocket 連線數（實時）
Panel: Web vs 其他平台 對話量比例（Pie chart）
Panel: Web 登入失敗率（時間序列）
Panel: Web 訊息 p95 延遲（與 webhook 平台對比）
Panel: 活躍 Web Sessions 數量（Gauge）
```

---

## 部署架構

### Docker Compose（Phase Web 增量）

```yaml
# Phase 3 docker-compose.yml 新增以下服務：

services:
  omnibot-api:
    # Phase 3 既有的 environment 之外，新增：
    environment:
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - JWT_ALGORITHM=HS256
      - WEB_CORS_ORIGINS=https://omnibot.example.com
    ports:
      - "8000:8000"
      - "8001:8001"  # WebSocket 專用 port（可與 HTTP 分離）

  redis:
    # Phase 3 既有的 TLS/AUTH 之外，確認有以下功能：
    # - Pub/Sub 訂閱（ws:session:* channels）
    # - Session 資料（web_sessions 表查詢 cache）
    command: >
      redis-server
        --requirepass ${REDIS_PASSWORD}
        --tls-port 6380
        --tls-cert-file /tls/redis.crt
        --tls-key-file /tls/redis.key
        --activerehashing yes
        --notify-keyspace-events Ex

  # Nginx（Phase Web 新增，反向代理 + WebSocket 支援）
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/web.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/certs:ro
    depends_on:
      - omnibot-api

  # 靜態前端（Phase Web 新增，CDN 部署亦可）
  web-frontend:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./frontend/dist:/usr/share/nginx/html:ro
```

### Nginx WebSocket 代理配置

```nginx
# nginx/web.conf
upstream omnibot_backend {
    server omnibot-api:8000;
}

upstream omnibot_websocket {
    server omnibot-api:8001;
}

server {
    listen 443 ssl http2;
    server_name omnibot.example.com;

    ssl_certificate /certs/fullchain.pem;
    ssl_certificate_key /certs/privkey.pem;

    # WebSocket 代理
    location /ws/chat {
        proxy_pass http://omnibot_websocket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;   # 24hr max connection
        proxy_send_timeout 86400;
    }

    # REST API
    location /api/ {
        proxy_pass http://omnibot_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 靜態資產
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
        expires 1d;
        add_header Cache-Control "public, no-transform";
    }
}
```

### Kubernetes 部署增量

```yaml
# Phase 3 Kubernetes 部署新增：

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: omnibot-web-config
data:
  JWT_SECRET_KEY: "$(JWT_SECRET_KEY)"
  WEB_CORS_ORIGINS: "https://omnibot.example.com"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: omnibot-api
spec:
  template:
    spec:
      containers:
        - name: omnibot
          envFrom:
            - configMapRef:
                name: omnibot-web-config
          ports:
            - containerPort: 8000
            - containerPort: 8001  # WebSocket

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: omnibot-web-ingress
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "86400"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "86400"
    nginx.ingress.kubernetes.io/use-regex: "true"
spec:
  rules:
    - host: omnibot.example.com
      http:
        paths:
          - path: /ws/chat
            pathType: Prefix
            backend:
              service:
                name: omnibot-api
                port:
                  number: 8001
          - path: /api/
            backend:
              service:
                name: omnibot-api
                port:
                  number: 8000
          - path: /
            backend:
              service:
                name: web-frontend
                port:
                  number: 80
```

---

## Web OAuth 整合（Social Login）

### Google OAuth 流程

```python
# app/web/oauth/google.py
import httpx
from dataclasses import dataclass

GOOGLE_OAUTH_URL = "https://oauth2.googleapis.com"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

class GoogleOAuth:
    """Google OAuth 2.0 登入整合"""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    def get_authorization_url(self, state: str) -> str:
        # 產生 OAuth 授權 URL，前端 redirect 到此 URL
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
        }
        query = urlencode(params)
        return f"{GOOGLE_OAUTH_URL}/auth?{query}"

    async def exchange_code(self, code: str) -> dict:
        """用 authorization code 換取 access_token"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GOOGLE_OAUTH_URL}/token",
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_user_info(self, access_token: str) -> "GoogleUserInfo":
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            data = resp.json()
            return GoogleUserInfo(
                subject=data["id"],
                email=data["email"],
                name=data.get("name", ""),
                picture=data.get("picture", ""),
            )

@dataclass(frozen=True)
class GoogleUserInfo:
    subject: str   # Google user ID
    email: str
    name: str
    picture: str
```

### OAuth 登入端點

```python
# app/api/web/oauth.py
@router.get("/login/{provider}")  # provider = google | github | line
async def oauth_login(
    provider: str,
    request: Request,
    db,
):
    """OAuth 登入第一步：產生授權 URL"""
    oauth = get_oauth_provider(provider)
    state = secrets.token_urlsafe(32)
    # 將 state 寫入 Redis（10 分鐘 TTL）防 CSRF
    db.set_oauth_state(state, {"provider": provider, "created_at": time.time()})

    redirect_url = oauth.get_authorization_url(state)
    return {"redirect_url": redirect_url}

@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    db,
    tm: TokenManager,
    sm: WebSessionManager,
):
    """OAuth 登入第二步：兌換 token + 建立 session"""
    # CSRF 驗證
    saved_state = db.get_oauth_state(state)
    if saved_state is None or saved_state["provider"] != provider:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    oauth = get_oauth_provider(provider)
    token_data = await oauth.exchange_code(code)
    user_info = await oauth.get_user_info(token_data["access_token"])

    # 查或建立用戶
    user = db.get_or_create_oauth_user(
        provider=provider,
        subject=user_info.subject,
        email=user_info.email,
        name=user_info.name,
    )

    # 發放 JWT session
    session_id = str(uuid.uuid4())
    access_token = tm.create_access_token(user.user_id, session_id, user.role)
    refresh_token = tm.create_refresh_token(user.user_id, session_id)

    sm.create(session_id=session_id, user_id=user.user_id, ...)

    # 回傳（前端需 redirect 回 app 並帶上 token）
    return {
        "access_token": access_token,
        "user_id": user.user_id,
    }
```

---

## 安全考量

### Web 入口額外 Attack Surface

| 攻擊向量 | 緩解措施 |
|----------|----------|
| JWT 盜用 | httpOnly Cookie（refresh_token）；Access Token 短效（15min） |
| Refresh Token 盜用重放 | Rotation on use；發現重放立刻撤銷全數 session |
| Social Login 帳號劫持 | OAuth state CSRF token；email 驗證後才開通 |
| WebSocket 仿冒 | JWT 在 handshake 驗證，wss 加密傳輸 |
| 暴力破解登入 | Login rate limiting（5 次/分鐘）；帳戶鎖定（可選） |
| XSS（前端） | Content-Security-Policy；輸入輸出轉義（前端責任） |
| CSRF | SameSite=Strict Cookie；state token（OAuth） |
| WebSocket DoS | Connection per session 限制；每分鐘新 session 上限 |

### Content Security Policy

```html
<!-- 前端 index.html -->
<meta http-equiv="Content-Security-Policy"
  content="
    default-src 'self';
    script-src 'self';
    style-src 'self' 'unsafe-inline';
    connect-src 'self' wss://omnibot.example.com;
    img-src 'self' data: https:;
    frame-ancestors 'none';
  ">
```

---

## 與 Phase 1-3 的整合點對照

| 既有模組 | 整合方式 | 需修改 |
|---------|---------|--------|
| Platform enum | + WEB 成員 | 否（新增枚舉值） |
| UnifiedMessage | platform=WEB 直接復用 | 否 |
| HybridKnowledgeLayer | 完全直接復用 | 否 |
| InputSanitizer | 直接復用 | 否 |
| PIIMasking | 直接復用 | 否 |
| Emotion Analyzer | 直接復用 | 否 |
| Intent Router + DST | 直接復用 | 否 |
| Grounding Checks | 直接復用 | 否 |
| conversations 表 | 直接復用，platform=WEB | 否 |
| messages 表 | 直接復用 | 否 |
| user_feedback 表 | 直接復用 | 否 |
| RateLimiter | WebSessionRateLimiter 新類別 | 否（新增，不是修改） |
| RBAC | web_user / web_agent 角色新增 | 否（新增角色，不影響既有） |
| Redis Streams | AsyncMessageProcessor 不變 | 否 |
| Redis Pub/Sub | **新增**（WebSocket 廣播專用） | 否（Phase 3 無此功能） |
| Prometheus Metrics | + platform=web label + WS metrics | 否（擴展，不修改既有） |
| Structured Logger | 直接復用 | 否 |

---

## 開發任務 Phase Web

### Phase Web: Web 入口 MVP（3-4 週）

- [ ] `users` 表 Schema 擴展（password_hash, email, oauth_*）
- [ ] `web_sessions` 表建立
- [ ] `oauth_accounts` 表建立
- [ ] `token_revocation_log` 表建立
- [ ] `web_conversations` 表建立
- [ ] `TokenManager`（JWT 建立/驗證）
- [ ] `WebAuthMiddleware`（登入驗證 + session 管理）
- [ ] `WebSessionManager`（session CRUD + Redis 缓存）
- [ ] `argon2` 密碼雜湊工具
- [ ] POST `/api/v1/auth/login`
- [ ] POST `/api/v1/auth/register`
- [ ] POST `/api/v1/auth/refresh`（rotation on use）
- [ ] POST `/api/v1/auth/logout`
- [ ] GET `/api/v1/auth/me`
- [ ] Google OAuth 流程
- [ ] `WebSocketConnectionManager`（Redis Pub/Sub）
- [ ] `WebSocketHandler`（訊息處理循環）
- [ ] GET `/ws/chat`（WebSocket 端點）
- [ ] `WebPlatformAdapter`
- [ ] `WebRateLimiter`
- [ ] CORS 配置
- [ ] Prometheus WebSocket metrics
- [ ] Nginx WebSocket proxy 配置
- [ ] Docker Compose Phase Web 增量
- [ ] Kubernetes Phase Web 增量
- [ ] Grafana Web Dashboard 新增 panels
- [ ] 前端 Chat UI（MVP）
- [ ] 前端登入/註冊介面
- [ ] 前端 Social Login 按鈕

---

## 驗收標準 Phase Web

| KPI | 目標 | 測試方法 |
|-----|------|----------|
| Web FCR | >= 75% | ODD SQL（platform=WEB filter） |
| p95 WebSocket 延遲 | < 1.5s | WebSocket ping/pong 測量 |
| 登入轉化率 | > 90% | 成功登入 / 嘗試登入 |
| Refresh Token Rotation | 100% | 自動化測試：refresh 後舊 token 失效 |
| Session 安全 | 0 token reuse 漏洞 | 滲透測試 |
| WebSocket 斷線復原 | < 5s | 人工切換網路測試 |
| CORS 配置 | 無漏洞 | 自動化 CORS check |
| 同時 WebSocket 連線 | 支援 >= 1000/實例 | 負載測試 |

---

## 與 Phase 4 的橋接

若 Phase Web 完成後需要擴展，建議方向（Phase 4 候選）：

| 功能 | 說明 |
|------|------|
| 客服 Agent 即時接管 | WebSocket 訊息轉向人類客服 |
| 多人對話（Group Chat） | 每個 room 一個 Redis channel |
| Widget 嵌入 | 可在任何網站嵌入的 iframe snippet |
| 視訊/語音整合 | WebRTC gateway |
| 推送通知（Web Push） | Service Worker + Web Push API |

---

*Phase: Web*
*文件版本: v1.0*
*最後更新: 2026-05-01*
