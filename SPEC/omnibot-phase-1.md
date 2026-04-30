# OmniBot Phase 1: MVP 基礎

---

## 專案概述

| 項目 | 內容 |
|--------|------|
| **專案名稱** | OmniBot - 多平台客服機器人 |
| **階段** | Phase 1（MVP 基礎） |
| **目標** | 50% FCR + 規則匹配 + 安全上線 |
| **核心原則** | 單一知識庫、安全左移、可觀測性左移 |
| **開發時間** | 3-4 週 |
| **前置條件** | 無 |

### 程式碼慣例

> 本規格書中所有 `db.execute(sql, params)` 為簡化寫法，代表「執行 SQL 並回傳結果列表（list[dict]）」。
> 實作時應使用具體 DB client（如 `asyncpg`、`psycopg`）的對應 API（`.fetch()`、`.fetchone()` 等）。
> 所有 `KnowledgeResult.id = -1` 代表非知識庫來源（如轉接），實作時應以此判斷。

---

## 商業目標

| KPI | Phase 1 目標 | 實現路徑 |
|-----|-------------|----------|
| **首問解決率 (FCR)** | 50% | 規則匹配 Layer 1 + 兜底轉接 |
| **CSAT 提升** | +15% | 快速回應常見 FAQ |
| **p95 回應延遲** | < 3.0s | 規則匹配低延遲 |
| **平台支援** | 2 個（Telegram + LINE） | 後續階段擴充 |

### 知識檢索策略（Phase 1）

| 知識類型 | 可用 | 說明 |
|-----------|------|------|
| **Layer 1: 規則匹配** | Y | SQL 精確匹配 + 關鍵字 |
| **Layer 2: RAG 向量檢索** | - | Phase 2 |
| **Layer 3: LLM 生成** | - | Phase 2 |
| **Layer 4: 人工轉接** | Y | 兜底（無 SLA，Phase 2 加入） |

> **說明**：Phase 1 僅啟用 Layer 1 + Layer 4。未匹配的查詢全部進入轉接佇列。FCR 僅計算 Layer 1 成功回覆的案件。

---

## 系統架構 Phase 1

```
+---------------------------------------------------------------------+
|                    OmniBot Phase 1 架構                              |
+---------------------------------------------------------------------+

  +--------------+  +--------------+
  |  Telegram   |  |    LINE     |
  |   (Bot)     |  |  (Official) |
  +------+------+  +------+------+
         |               |
  +------+---------------+----------------------------------------+
  |              API Gateway                                      |
  |            - Rate Limiting (Token Bucket)                     |
  |            - TLS 終結                                         |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Platform Adapter Layer                            |
  |            - 統一消息格式 (UnifiedMessage)                     |
  |            - Webhook 簽名驗證（Telegram + LINE）              |
  |            - 用戶身份映射                                      |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Input Sanitizer (L2)                              |
  |            - 字元正規化 (NFKC)                                |
  |            - 控制字元移除                                      |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              PII Masking (L4)                                  |
  |            - 基礎 PII 去識別化                                |
  |            - 電話/Email/地址 遮蔽                              |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Knowledge Layer（僅 Layer 1）                     |
  |            - SQL 精確匹配                                      |
  |            - PostgreSQL LIKE 查詢                               |
  |            - 關鍵字索引                                        |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Response Generator                                |
  |            - 規則匹配回覆                                      |
  |            - 未匹配 → 轉接人工                                 |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Structured Logger                                 |
  |            - JSON 結構化日誌                                   |
  |            - 日誌級別策略                                      |
  +---------------------------------------------------------------+
```

---

## API 設計 Phase 1

### Webhook 端點

```yaml
paths:
  /api/v1/webhook/telegram:
    post:
      summary: Telegram Bot Webhook
      security:
        - TelegramTokenAuth: []
      responses:
        '200':
          description: OK
        '401':
          description: 簽名驗證失敗
        '429':
          description: Rate Limit 超出

  /api/v1/webhook/line:
    post:
      summary: LINE Messaging API Webhook
      security:
        - LineSignatureAuth: []
      responses:
        '200':
          description: OK
        '401':
          description: 簽名驗證失敗
        '429':
          description: Rate Limit 超出
```

### 管理 API

```yaml
paths:
  /api/v1/knowledge:
    get:
      summary: 查詢知識庫
      parameters:
        - name: q
          in: query
          schema: { type: string }
        - name: category
          in: query
          schema: { type: string }
        - name: page
          in: query
          schema: { type: integer, default: 1 }
        - name: limit
          in: query
          schema: { type: integer, default: 20, maximum: 100 }
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PaginatedResponse'

    post:
      summary: 新增知識條目（Phase 1 無 RBAC，Phase 3 加入）

  /api/v1/knowledge/{id}:
    put:
      summary: 更新知識條目
    delete:
      summary: 刪除知識條目

  /api/v1/knowledge/bulk:
    post:
      summary: 批次匯入知識

  /api/v1/conversations:
    get:
      summary: 查詢對話記錄
      parameters:
        - name: page
          in: query
          schema: { type: integer, default: 1 }
        - name: limit
          in: query
          schema: { type: integer, default: 20, maximum: 100 }
        - name: platform
          in: query
          schema: { type: string, enum: [telegram, line, messenger, whatsapp] }
        - name: started_after
          in: query
          schema: { type: string, format: date-time }
        - name: started_before
          in: query
          schema: { type: string, format: date-time }
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  success: { type: boolean }
                  data:
                    type: array
                    items:
                      type: object
                      properties:
                        id: { type: integer }
                        unified_user_id: { type: string, format: uuid }
                        platform: { type: string }
                        started_at: { type: string, format: date-time }
                        ended_at: { type: string, format: date-time, nullable: true }
                        status: { type: string }
                  total: { type: integer }
                  page: { type: integer }
                  limit: { type: integer }
                  has_next: { type: boolean }
        '401': { description: Unauthorized }
        '422': { description: Validation error }

  /api/v1/health:
    get:
      summary: 健康檢查端點
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  status: { type: string, enum: [healthy, degraded, unhealthy] }
                  postgres: { type: boolean }
                  redis: { type: boolean }
                  uptime_seconds: { type: number }
```

### 統一回應格式

```python
from dataclasses import dataclass
from typing import TypeVar, Generic, Optional, List

T = TypeVar("T")

@dataclass
class ApiResponse(Generic[T]):
    success: bool
    data: Optional[T]
    error: Optional[str] = None
    error_code: Optional[str] = None

@dataclass
class PaginatedResponse(ApiResponse[List[T]], Generic[T]):
    total: int = 0
    page: int = 1
    limit: int = 20
    has_next: bool = False
```

### 錯誤碼規範

| 錯誤碼 | HTTP Status | 說明 |
|--------|-------------|------|
| `AUTH_INVALID_SIGNATURE` | 401 | Webhook 簽名驗證失敗 |
| `RATE_LIMIT_EXCEEDED` | 429 | 請求頻率超出限制 |
| `KNOWLEDGE_NOT_FOUND` | 404 | 知識條目不存在 |
| `VALIDATION_ERROR` | 422 | 請求參數驗證失敗 |
| `INTERNAL_ERROR` | 500 | 內部伺服器錯誤 |

> **Phase 2 新增**：`LLM_TIMEOUT (504)`。**Phase 3 新增**：`AUTH_TOKEN_EXPIRED (401)`、`AUTHZ_INSUFFICIENT_ROLE (403)`（此碼已預先定義於 Phase 1 規格表中，但 Phase 1 實作期間不會被觸發，Phase 3 RBAC 上線後才會出現）。

---

## Webhook 簽名驗證（Telegram + LINE）

```python
import hmac
import hashlib
import base64
from abc import ABC, abstractmethod

class WebhookVerifier(ABC):
    @abstractmethod
    def verify(self, body: bytes, signature: str) -> bool: ...

class LineWebhookVerifier(WebhookVerifier):
    def __init__(self, channel_secret: str):
        self.channel_secret = channel_secret.encode("utf-8")

    def verify(self, body: bytes, signature: str) -> bool:
        digest = hmac.new(
            self.channel_secret, body, hashlib.sha256
        ).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

class TelegramWebhookVerifier(WebhookVerifier):
    def __init__(self, bot_token: str):
        self.secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()

    def verify(self, body: bytes, signature: str) -> bool:
        expected = hmac.new(
            self.secret_key, body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

VERIFIERS: dict[str, type[WebhookVerifier]] = {
    "line": LineWebhookVerifier,
    "telegram": TelegramWebhookVerifier,
}
```

> **Phase 2 新增**：`MessengerWebhookVerifier`、`WhatsAppWebhookVerifier`。

---

## 統一消息格式

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

class Platform(Enum):
    TELEGRAM = "telegram"
    LINE = "line"
    MESSENGER = "messenger"    # Phase 2 啟用
    WHATSAPP = "whatsapp"      # Phase 2 啟用

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    STICKER = "sticker"
    LOCATION = "location"
    FILE = "file"

@dataclass(frozen=True)
class UnifiedMessage:
    """跨平台統一消息格式（immutable）"""
    platform: Platform
    platform_user_id: str
    unified_user_id: Optional[str]
    message_type: MessageType
    content: str
    raw_payload: dict = field(default_factory=dict)
    received_at: datetime = field(default_factory=datetime.utcnow)
    reply_token: Optional[str] = None  # LINE 特有

@dataclass(frozen=True)
class UnifiedResponse:
    """統一回覆格式"""
    content: str
    source: str  # rule | rag | wiki | escalate
    confidence: float
    knowledge_id: Optional[int] = None
    emotion_adjustment: Optional[str] = None  # Phase 2 啟用
```

---

## 輸入清理 L2（字元正規化）

```python
import unicodedata

class InputSanitizer:
    """
    L2 輸入清理：僅做字元正規化。
    不做 pattern matching（由 Phase 2 的 PromptInjectionDefense L3 負責）。
    """

    def sanitize(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        text = "".join(c for c in text if c.isprintable() or c in "\n\t")
        return text.strip()
```

---

## 基礎 PII 去識別化 L4

```python
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class PIIMaskResult:
    masked_text: str
    mask_count: int
    pii_types: list[str]

class PIIMasking:
    """
    基礎 PII 去識別化（Phase 1）。
    Scope 聲明：僅支援台灣地區格式（電話、地址、Email）。
    Phase 2 新增：信用卡 Luhn 校驗。
    """

    PATTERNS: dict[str, re.Pattern] = {
        "phone": re.compile(r"\b(?:\d{4}-\d{3,4}-\d{3,4}|\d{10,11})\b"),
        "email": re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        ),
        "address": re.compile(
            r"(?:(?:台|臺)(?:北|中|南|東)?|新北|桃園|高雄|基隆|新竹|嘉義|"
            r"苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|澎湖|金門|連江)"
            r"(?:市|縣).{2,30}?(?:路|街|巷|弄|號|樓)"
        ),
    }

    SENSITIVE_KEYWORDS: list[re.Pattern] = [
        re.compile(p) for p in [r"密碼", r"銀行帳戶", r"信用卡號", r"提款卡"]
    ]

    def mask(self, text: str) -> PIIMaskResult:
        masked = text
        count = 0
        pii_types: list[str] = []

        for pii_type, pattern in self.PATTERNS.items():
            matches = list(pattern.finditer(masked))
            for match in reversed(matches):  # 從後往前替換避免偏移
                start, end = match.start(), match.end()
                masked = masked[:start] + f"[{pii_type}_masked]" + masked[end:]
                count += 1
                if pii_type not in pii_types:
                    pii_types.append(pii_type)

        return PIIMaskResult(masked_text=masked, mask_count=count, pii_types=pii_types)

    def should_escalate(self, text: str) -> bool:
        return any(p.search(text) for p in self.SENSITIVE_KEYWORDS)
```

---

## 基礎速率限制

```python
import time
from dataclasses import dataclass, field

@dataclass
class TokenBucket:
    """令牌桶速率限制器"""
    capacity: int
    refill_rate: float  # tokens per second
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)

    def __post_init__(self):
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

class RateLimiter:
    """per-platform per-user 速率限制"""

    def __init__(self, default_rps: int = 100):
        self._buckets: dict[str, TokenBucket] = {}
        self._default_rps = default_rps

    def check(self, platform: str, user_id: str) -> bool:
        key = f"{platform}:{user_id}"
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                capacity=self._default_rps,
                refill_rate=float(self._default_rps),
            )
        return self._buckets[key].consume()
```

---

## Knowledge Layer Phase 1（僅規則匹配）

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class KnowledgeResult:
    id: int
    content: str
    confidence: float
    source: str = ""           # rule | rag | wiki | escalate
    knowledge_id: Optional[int] = None

class KnowledgeLayerV1:
    """Phase 1：僅規則匹配 + 轉接兜底"""

    def query(self, db, query_text: str) -> KnowledgeResult:
        result = self._rule_match(db, query_text)
        if result is not None and result.confidence > 0.7:
            return result

        return self._escalate(query_text, reason="no_rule_match")

    def _rule_match(self, db, query_text: str) -> Optional[KnowledgeResult]:
        results = self._rule_match_list(db, query_text)
        return results[0] if results else None

    def _rule_match_list(self, db, query_text: str) -> list[KnowledgeResult]:
        rows = db.execute(
            """
            SELECT id, question, answer, keywords
            FROM knowledge_base
            WHERE is_active = TRUE
              AND (question ILIKE %s OR %s = ANY(keywords))
            ORDER BY version DESC
            LIMIT 5
            """,
            (f"%{query_text}%", query_text),
        )
        return [
            KnowledgeResult(
                id=row["id"],
                content=row["answer"],
                confidence=0.95 if query_text.lower() in row["question"].lower() else 0.7,
                source="rule",
                knowledge_id=row["id"],
            )
            for row in rows
        ]

    def _escalate(self, query_text: str, reason: str) -> KnowledgeResult:
        return KnowledgeResult(
            id=-1,
            content="正在為您轉接人工客服，請稍候...",
            confidence=0.0,
            source="escalate",
        )
```

> **Phase 2 升級為 `HybridKnowledgeV7`**：新增 RAG Layer 2、RRF 融合、LLM Layer 3。

---

## 基礎人工轉接（無 SLA）

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class EscalationRequest:
    conversation_id: int
    reason: str  # no_rule_match | sensitive_content

class BasicEscalationManager:
    """Phase 1：基礎轉接，無 SLA 追蹤。Phase 2 升級為 EscalationManager。"""

    def __init__(self, db):
        self.db = db

    def create(self, request: EscalationRequest) -> int:
        row = self.db.execute(
            """
            INSERT INTO escalation_queue (conversation_id, reason)
            VALUES (%s, %s)
            RETURNING id
            """,
            (request.conversation_id, request.reason),
        )
        return row["id"]

    def assign(self, escalation_id: int, agent_id: str) -> None:
        self.db.execute(
            """
            UPDATE escalation_queue
            SET assigned_agent = %s, picked_at = NOW()
            WHERE id = %s AND resolved_at IS NULL
            """,
            (agent_id, escalation_id),
        )

    def resolve(self, escalation_id: int) -> None:
        self.db.execute(
            """
            UPDATE escalation_queue
            SET resolved_at = NOW()
            WHERE id = %s
            """,
            (escalation_id,),
        )
```

---

## 結構化日誌

```python
import json
import logging
from datetime import datetime
from typing import Any

class StructuredLogger:
    """JSON 結構化日誌（Phase 1 即啟用）"""

    LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    def __init__(self, service: str = "omnibot"):
        self.service = service
        self.logger = logging.getLogger(service)

    def log(self, level: str, message: str, **kwargs: Any) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "service": self.service,
            "message": message,
            **kwargs,
        }
        self.logger.log(self.LOG_LEVELS.get(level, logging.INFO), json.dumps(entry))

    def info(self, message: str, **kwargs: Any) -> None:
        self.log("INFO", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self.log("ERROR", message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        self.log("WARN", message, **kwargs)
```

### 日誌級別策略

| 級別 | 用途 | 範例 |
|------|------|------|
| DEBUG | 開發調試 | SQL 查詢參數、匹配分數 |
| INFO | 業務事件 | 新對話開始、規則匹配成功 |
| WARN | 非致命異常 | 匹配信心度偏低、PII 偵測 |
| ERROR | 致命錯誤 | DB 連線中斷 |
| CRITICAL | 系統緊急 | 安全事件 |

---

## 資料庫 Schema Phase 1

> **設計原則**：Phase 1 建立所有核心表（含後續階段會用到的欄位），避免 Phase 2/3 需要 ALTER TABLE。預留欄位初始為 NULL 即可。

```sql
-- ============================================================
-- 用戶統一表（跨平台）
-- ============================================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    unified_user_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    platform VARCHAR(20) NOT NULL,
    platform_user_id VARCHAR(100) NOT NULL,
    profile JSONB,
    preference_tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(platform, platform_user_id)
);

CREATE INDEX idx_users_platform_uid ON users (platform, platform_user_id);

-- ============================================================
-- 對話歷史（含 ODD 追蹤欄位）
-- ============================================================
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    unified_user_id UUID REFERENCES users(unified_user_id),
    platform VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    satisfaction_score FLOAT,
    first_contact_resolution BOOLEAN,
    resolution_cost FLOAT,                   -- 成本追蹤（Phase 3 使用）
    response_time_ms INTEGER,
    scope_type VARCHAR(20) DEFAULT 'in_scope',
    dst_state JSONB                          -- DST 狀態快照（Phase 2 使用）
);

CREATE INDEX idx_conversations_started ON conversations (started_at);
CREATE INDEX idx_conversations_user ON conversations (unified_user_id);
CREATE INDEX idx_conversations_platform ON conversations (platform, started_at);

-- ============================================================
-- 訊息記錄
-- ============================================================
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role VARCHAR(20) NOT NULL,               -- user | assistant | system
    content TEXT NOT NULL,
    intent_detected VARCHAR(50),
    sentiment_category VARCHAR(20),          -- positive/neutral/negative（Phase 2 使用）
    sentiment_intensity FLOAT,               -- 0.0 - 1.0（Phase 2 使用）
    confidence_score FLOAT,
    knowledge_source VARCHAR(20),            -- rule/rag/wiki/escalate
    user_feedback VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages (conversation_id);
CREATE INDEX idx_messages_created ON messages (created_at);

-- ============================================================
-- 知識庫（含向量欄位，Phase 2 啟用 pgvector）
-- ============================================================
CREATE TABLE knowledge_base (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    keywords TEXT[],
    embeddings vector(384),                  -- 對齊 MiniLM-L12 輸出維度（Phase 2 填充）
    embedding_model VARCHAR(100) NOT NULL
        DEFAULT 'paraphrase-multilingual-MiniLM-L12-v2',
    version INTEGER DEFAULT 1,
    contains_pii BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kb_category ON knowledge_base (category);
CREATE INDEX idx_kb_keywords ON knowledge_base USING GIN (keywords);
-- Phase 2 建立: CREATE INDEX idx_kb_embeddings ON knowledge_base
--     USING ivfflat (embeddings vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- 平台適配器配置
-- ============================================================
CREATE TABLE platform_configs (
    platform VARCHAR(20) PRIMARY KEY,
    enabled BOOLEAN DEFAULT TRUE,
    config JSONB,
    rate_limit_rps INTEGER DEFAULT 100,
    max_session_duration_sec INTEGER DEFAULT 1800,
    webhook_secret_key_ref VARCHAR(100),      -- 密鑰管理器引用，非明文
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 人工轉接佇列
-- ============================================================
CREATE TABLE escalation_queue (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) UNIQUE,
    reason VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 0,              -- 0=normal, 1=high, 2=urgent
    assigned_agent UUID REFERENCES users(unified_user_id),
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    picked_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    sla_deadline TIMESTAMPTZ                 -- Phase 2 啟用
);

CREATE INDEX idx_escalation_pending ON escalation_queue (queued_at)
    WHERE resolved_at IS NULL;

-- ============================================================
-- 用戶回饋收集
-- ============================================================
CREATE TABLE user_feedback (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    message_id INTEGER REFERENCES messages(id),
    feedback VARCHAR(20) NOT NULL CHECK (feedback IN ('thumbs_up', 'thumbs_down')),
    comment TEXT,                             -- 可選回饋文字
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 安全日誌
-- ============================================================
CREATE TABLE security_logs (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    layer VARCHAR(10) NOT NULL,              -- L0/L1/L2/L3/L4/L5
    blocked BOOLEAN DEFAULT FALSE,
    block_reason TEXT,
    source_ip INET,
    platform VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_security_logs_date ON security_logs (created_at);
```

---

## ODD 驗證 SQL Phase 1

```sql
-- FCR 首問解決率（僅 in_scope）
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN first_contact_resolution THEN 1 ELSE 0 END) AS fcr,
    ROUND(
        SUM(CASE WHEN first_contact_resolution THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(*), 0), 2
    ) AS fcr_rate_pct
FROM conversations
WHERE started_at > NOW() - INTERVAL '30 days'
  AND scope_type = 'in_scope'
  AND first_contact_resolution IS NOT NULL;

-- 回應延遲
SELECT
    platform,
    AVG(response_time_ms) AS avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) AS p95_latency_ms
FROM conversations
WHERE started_at > NOW() - INTERVAL '30 days'
  AND response_time_ms IS NOT NULL
GROUP BY platform;

-- 知識層命中（Phase 1 僅 rule + escalate）
SELECT
    knowledge_source,
    COUNT(*) AS total,
    AVG(confidence_score) AS avg_confidence
FROM messages
WHERE role = 'assistant'
  AND created_at > NOW() - INTERVAL '7 days'
  AND knowledge_source IS NOT NULL
GROUP BY knowledge_source;
```

---

## Docker Compose（開發環境）

```yaml
services:
  omnibot-api:
    build: .
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://omnibot:${DB_PASSWORD}@postgres:5432/omnibot
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: omnibot
      POSTGRES_USER: omnibot
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U omnibot"]
      interval: 10s

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s

volumes:
  pgdata:
```

---

## 開發任務 Phase 1

### Phase 1: MVP 基礎（3-4 週）
- [ ] PostgreSQL Schema（全部核心表 + 索引）
- [ ] Platform Adapter（Telegram + LINE）
- [ ] Webhook 簽名驗證（Telegram + LINE）
- [ ] 統一消息格式（UnifiedMessage / UnifiedResponse）
- [ ] 統一回應格式（ApiResponse / PaginatedResponse）
- [ ] 輸入清理 L2（字元正規化）
- [ ] 基礎 PII 去識別化 L4（電話/Email/地址）
- [ ] Rate Limiter（Token Bucket）
- [ ] 規則匹配 Knowledge Layer 1
- [ ] 基礎人工轉接（無 SLA）
- [ ] 結構化日誌（JSON Logger）
- [ ] 健康檢查端點
- [ ] Docker Compose 開發環境
- [ ] 基礎 ODD SQL 查詢

---

## 驗收標準 Phase 1

| KPI | 目標 | 測試方法 |
|-----|------|----------|
| FCR | >= 50% | ODD SQL 查詢 |
| p95 延遲 | < 3.0s | 手動壓測 |
| 平台支援 | Telegram + LINE | 功能測試 |
| Webhook 驗證 | 100% 驗證 | 滲透測試 |
| PII 遮蔽 | 電話/Email/地址 | 單元測試 |
| 日誌 | JSON 結構化 | 日誌檢查 |

---

*Phase: 1*
*文件版本: v7.0*
*最後更新: 2026-04-15*
