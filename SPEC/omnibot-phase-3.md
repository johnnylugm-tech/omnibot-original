# OmniBot Phase 3: 企業級 + Production Ready

---

## 專案概述

| 項目 | 內容 |
|--------|------|
| **專案名稱** | OmniBot - 多平台客服機器人 |
| **階段** | Phase 3（企業級 + Production Ready） |
| **目標** | 90% FCR + 99.9% 可用性 + RBAC + A/B + 完整部署 |
| **前置條件** | Phase 1 + Phase 2 完成 |
| **開發時間** | 2-3 週 |

---

## 商業目標

| KPI | Phase 3 目標 | Phase 2 基線 | 實現路徑 |
|-----|-------------|-------------|----------|
| **首問解決率 (FCR)** | 90% | 80% | A/B 優化 + 持續迭代 |
| **CSAT 提升** | +50% | +35% | 全面優化 |
| **系統可用性** | 99.9% | - | 多副本 + 自動故障轉移 |
| **p95 回應延遲** | < 1.0s | < 1.5s | Redis 快取 + 異步處理 |
| **災備復原時間** | < 5 分鐘 | - | 自動化復原 |
| **月成本** | < $500（實際估算 ~$210/月） | - | 成本模型追蹤 |

> **成本說明**：`~$210/月` 為 LLM API 基礎估算（假設 10 萬對話，Layer 2 RAG 40% 覆蓋率）。`< $500/月` 為含 GPU 推理、Embedding 計算、備用硬體的實際部署成本上限。兩者假設不同，均為合理估算。

### CSAT 量化指標（最終版）

| 體驗維度 | 量化指標 | 權重 | 目標基準 |
|----------|----------|------|----------|
| **響應速度** | p95 Latency | 40% | < 1.0s |
| **擬人化深度** | SSRA Scale（Lyra 等級）| 20% | 中等偏高 |
| **語言品質** | LLM-as-a-judge (Politeness) | 20% | > 4.5/5.0 |
| **解決方案質量** | LLM-as-a-judge (Accuracy) | 20% | 100% 知識對齊 |

### SLA 定義

| 指標 | SLA | 告警閾值 | 監控 |
|------|-----|---------|------|
| 可用性 | 99.9% / 月 | < 99.95% | Prometheus |
| p95 延遲 | < 1.0s | > 0.8s | Prometheus |
| 錯誤率 | < 1% | > 0.5% | Prometheus |
| 轉接 SLA 遵守 | >= 95% | < 90% | ODD SQL |

---

## 系統架構 Phase 3（完整版）

```
+---------------------------------------------------------------------+
|                    OmniBot Phase 3 完整架構                          |
+---------------------------------------------------------------------+

  +--------------+  +--------------+  +--------------+  +--------------+
  |  Telegram   |  |    LINE     |  | Messenger   |  |  WhatsApp   |
  +------+------+  +------+------+  +------+------+  +------+------+
         |               |               |               |
  +------+---------------+---------------+---------------+------------+
  |              API Gateway                                          |
  |            - Rate Limiting (Token Bucket) ← Phase 1               |
  |            - TLS 終結 ← Phase 1                                   |
  |            - IP 白名單（Phase 3 新增）                             |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Platform Adapter Layer ← Phase 1+2                |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Input Sanitizer L2 ← Phase 1                     |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Prompt Injection Defense L3 ← Phase 2             |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              PII Masking L4 ← Phase 2                         |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Emotion Analyzer ← Phase 2                        |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Intent Router + DST ← Phase 2                     |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Hybrid Knowledge Layer ← Phase 2                  |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Grounding Checks L5 ← Phase 2                     |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Response Generator                                |
  |            + A/B Testing Variant 選擇（Phase 3 新增）           |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              RBAC Enforcement（Phase 3 新增）                   |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              Observability Layer（Phase 3 完整化）              |
  |            - Structured Logger ← Phase 1                       |
  |            - Prometheus Metrics ← Phase 2                      |
  |            - OpenTelemetry Tracing（Phase 3 新增）              |
  |            - Grafana Dashboards（Phase 3 新增）                 |
  |            - 告警規則（Phase 3 新增）                           |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              高可用性層（Phase 3 新增）                         |
  |            - Redis Streams 異步處理                             |
  |            - 指數退避重試                                       |
  |            - TDE 加密                                           |
  |            - 負載均衡                                           |
  +---------------------------------------------------------------+
                             |
  +---------------------------------------------------------------+
  |              部署與災備（Phase 3 新增）                         |
  |            - Docker Compose ← Phase 1（升級）                   |
  |            - Kubernetes                                         |
  |            - 備份 / Rollback / 降級策略                         |
  +---------------------------------------------------------------+
```

---

## 新增錯誤碼（Phase 3）

| 錯誤碼 | HTTP Status | 說明 |
|--------|-------------|------|
| `AUTH_TOKEN_EXPIRED` | 401 | Bearer Token 過期 |
| `AUTHZ_INSUFFICIENT_ROLE` | 403 | RBAC 權限不足 |

> 完整錯誤碼表：Phase 1 定義 5 個 + Phase 2 定義 1 個 + Phase 3 定義 2 個 = 共 8 個。

---

## RBAC 權限管理（Phase 3 新增）

### 權限定義

```python
from functools import wraps
from typing import Callable

ROLE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "admin": {
        "knowledge": ["read", "write", "delete"],
        "escalate": ["read", "write"],
        "audit": ["read"],
        "experiment": ["read", "write", "delete"],
        "system": ["read", "write"],
    },
    "editor": {
        "knowledge": ["read", "write"],
        "escalate": ["read"],
        "audit": [],
        "experiment": ["read"],
        "system": [],
    },
    "agent": {
        "knowledge": ["read"],
        "escalate": ["write"],
        "audit": [],
        "experiment": [],
        "system": [],
    },
    "auditor": {
        "knowledge": ["read"],
        "escalate": ["read"],
        "audit": ["read"],
        "experiment": ["read"],
        "system": ["read"],
    },
}
```

### RBAC Enforcement 中間件

```python
class RBACEnforcer:
    """RBAC 權限檢查與 enforcement"""

    def __init__(self, permissions: dict[str, dict[str, list[str]]] = ROLE_PERMISSIONS):
        self._permissions = permissions

    def check(self, role: str, resource: str, action: str) -> bool:
        role_perms = self._permissions.get(role, {})
        allowed_actions = role_perms.get(resource, [])
        return action in allowed_actions

    def require(self, resource: str, action: str) -> Callable:
        """裝飾器：要求特定權限"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                request = kwargs.get("request") or args[0]
                user_role = getattr(request, "user_role", None)

                if not user_role or not self.check(user_role, resource, action):
                    raise PermissionError(
                        f"Role '{user_role}' lacks '{action}' on '{resource}'"
                    )
                return await func(*args, **kwargs)
            return wrapper
        return decorator

rbac = RBACEnforcer()

# 使用範例：
# @rbac.require("knowledge", "write")
# async def create_knowledge(request, ...): ...
```

### 高級 IP 白名單（Advanced IP Whitelisting）

#### 功能定義
API Gateway 需支援來源 IP 白名單過濾，僅允許已登記的 IP 區塊發送請求。

#### 資料結構
- 白名單格式：CIDR 表示法（例如：`203.0.113.0/24`、`198.51.100.0/24`）
- 最大登記數量：100 個 CIDR 區塊
- 儲存位置：`IP_WHITELIST_CIDRS` 環境變數（逗號分隔）
  - 或 `config/ip_whitelist.yaml`（Phase 3 擴展時）

#### 比對邏輯
- 對每一個連入請求，提取來源 IP：
  - 優先讀取 `X-Forwarded-For` 表頭，取**最左側（即第一個）IP**（原始客戶端）
  - 若無表頭，則使用 `request.client.host`（直接連線 IP）
- 檢查來源 IP 是否落在任一白名單 CIDR 區塊內
- 若無匹配：回應 `HTTP 403 Forbidden`，body 為空，request 不送至下游

#### 行為矩陣

| 情境 | 白名單有匹配 | 白名單無匹配 |
|------|-------------|-------------|
| 已在白名單的 IP | 允許通過 | 回 403 |
| 未在白名單的 IP | N/A | 回 403 |
| 白名單為空 | N/A | 回 403（fail-secure） |
| 格式異常的 IP | N/A | 回 403（fail-secure） |

#### 在攔截鏈中的順序

```
Rate Limiting → IP Whitelist → TLS → Platform Adapter → RBAC
```

- **Rate Limiting（Phase 1）**：在 IP 白名單檢查**之後**（IP 未通過則不消耗配額）
- **RBAC（Phase 3）**：在 IP 白名單檢查**之後**（IP 未通過則不送至 RBAC）

#### 實作位置
- 模組：`app/security/ip_whitelist.py`
- 主類別：`IPWhitelist`
- 初始化：`app/api/__init__.py`（模組層級單例）
- 钩入點：四個 webhook 端點（telegram/line/messenger/whatsapp）

#### 環境變數

| 變數 | 格式 | 預設值 |
|------|------|--------|
| `IP_WHITELIST_CIDRS` | 逗號分隔的 CIDR 字串 | ""（空 = 拒絕所有）|

#### 錯誤處理
- 無效 CIDR 格式：拋出 `IPWhitelistError`（啟動時驗證）
- 無效 IP 格式（`is_allowed`）：回 `False`（fail-secure，不拋例外）

### 管理 API 安全標註更新

```yaml
# Phase 3 為管理 API 加上 RBAC 保護
paths:
  /api/v1/knowledge:
    post:
      security:
        - BearerAuth: []
        - RBACPermission: [knowledge:write]
  /api/v1/knowledge/{id}:
    put:
      security:
        - BearerAuth: []
        - RBACPermission: [knowledge:write]
    delete:
      security:
        - BearerAuth: []
        - RBACPermission: [knowledge:delete]
  /api/v1/experiments:
    post:
      security:
        - BearerAuth: []
        - RBACPermission: [experiment:write]
```

---

## A/B Testing 框架（Phase 3 新增）

```python
import hashlib
from typing import Optional

class ABTestManager:
    def __init__(self, db, llm):
        self.db = db
        self.llm = llm

    def get_variant(self, user_id: str, experiment_id: int) -> str:
        """
        確定性 variant 分配。
        使用 hashlib.sha256 確保跨進程一致（非 Python hash()）。
        """
        key = f"{user_id}:{experiment_id}".encode("utf-8")
        digest = hashlib.sha256(key).hexdigest()
        variant_hash = int(digest[:8], 16) % 100

        experiment = self.db.get_experiment(experiment_id)
        split = experiment["traffic_split"]

        cumulative = 0
        for variant, percentage in split.items():
            cumulative += percentage
            if variant_hash < cumulative:
                return variant
        return "control"

    def run_experiment(
        self, experiment_id: int, query: str, user_id: str, context: dict
    ) -> str:
        variant = self.get_variant(user_id, experiment_id)
        experiment = self.db.get_experiment(experiment_id)
        prompt = experiment["variants"][variant]["prompt"]
        return self.llm.generate(query, context, system_prompt=prompt)

    def analyze_results(self, experiment_id: int) -> list:
        """查詢實驗結果"""
        return self.db.execute(
            """
            SELECT variant, metric_name, metric_value, sample_size
            FROM experiment_results
            WHERE experiment_id = %s
            """,
            (experiment_id,),
        )

    def auto_promote(
        self, experiment_id: int, metric: str = "csat", threshold: float = 0.05
    ) -> Optional[str]:
        """自動切換到優勢版本（含最小樣本量檢查）"""
        results = self.analyze_results(experiment_id)

        variants: dict[str, float] = {}
        sample_sizes: dict[str, int] = {}
        for r in results:
            variants[r.variant] = r.metric_value
            sample_sizes[r.variant] = r.sample_size

        if len(variants) < 2:
            return None

        # 最小樣本量檢查
        min_sample = 100
        if any(sample_sizes.get(v, 0) < min_sample for v in variants):
            return None

        best = max(variants, key=variants.get)
        others = [v for v in variants if v != best]

        diff = variants[best] - variants[others[0]]
        if diff >= threshold:
            self.db.execute(
                """
                UPDATE experiments
                SET status = 'completed', ended_at = NOW()
                WHERE id = %s
                """,
                (experiment_id,),
            )
            return best
        return None
```

---

## OpenTelemetry Tracing（Phase 3 新增）

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def setup_tracing(service_name: str = "omnibot") -> None:
    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

tracer = trace.get_tracer("omnibot")

# 使用範例
async def handle_message(message):
    with tracer.start_as_current_span("handle_message") as span:
        span.set_attribute("platform", message.platform.value)
        span.set_attribute("user_id", message.platform_user_id)

        with tracer.start_as_current_span("emotion_analysis"):
            emotion = analyze_emotion(message.content)
            span.set_attribute("emotion", emotion.category.value)

        with tracer.start_as_current_span("knowledge_query"):
            result = knowledge.query(message.content)
            span.set_attribute("knowledge_source", result.source)
            span.set_attribute("confidence", result.confidence)
```

---

## 告警規則（Phase 3 新增）

```yaml
groups:
  - name: omnibot
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.95, omnibot_response_duration_seconds) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "p95 延遲超過 1 秒 SLA"

      - alert: HighErrorRate
        expr: rate(omnibot_requests_total{status="error"}[5m]) / rate(omnibot_requests_total[5m]) > 0.05
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "錯誤率超過 5%"

      - alert: EscalationQueueBacklog
        expr: omnibot_escalation_queue_size > 50
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "轉接佇列積壓超過 50 件"

      - alert: SLABreach
        expr: increase(omnibot_escalation_sla_breach_total[1h]) > 5
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "過去 1 小時有超過 5 件 SLA 違規"
```

---

## Redis Streams 異步處理（Phase 3 新增）

```python
import redis.asyncio as aioredis
from redis.exceptions import ResponseError

class AsyncMessageProcessor:
    """
    Redis Streams 消費者群組。
    注意：使用 classmethod factory 建立實例，避免 __init__ 中 await。
    """

    def __init__(self, redis_client: aioredis.Redis, group: str = "omnibot"):
        self.redis = redis_client
        self.group = group

    @classmethod
    async def create(cls, redis_url: str, group: str = "omnibot") -> "AsyncMessageProcessor":
        redis_client = await aioredis.from_url(redis_url)
        instance = cls(redis_client, group)
        await instance._ensure_group()
        return instance

    async def _ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                "omnibot:messages",
                self.group,
                id="0",
                mkstream=True,
            )
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def consume(self, consumer: str, count: int = 10):
        streams = await self.redis.xreadgroup(
            self.group,
            consumer,
            {"omnibot:messages": ">"},
            count=count,
            block=5000,
        )
        return streams

    async def ack(self, message_id: str) -> None:
        await self.redis.xack("omnibot:messages", self.group, message_id)


## Redis Stream 訊息格式（Message Schema）

```
Stream Key: omnibot:messages
Consumer Group: omnibot
```

### 訊息 Payload 欄位定義

| 欄位名 | 型別 | 必填 | 說明 |
|--------|------|------|------|
| `message_id` | string (UUID) | 是 | 全域唯一訊息 ID |
| `conversation_id` | integer | 是 | 對話 ID（參照 `conversations.id`）|
| `platform` | string | 是 | 平台來源：`telegram` / `line` / `messenger` / `whatsapp` |
| `unified_user_id` | string (UUID) | 是 | 跨平台統一用戶 ID |
| `direction` | string | 是 | `inbound` / `outbound` |
| `content` | string | 是 | 訊息內容文本 |
| `timestamp` | string (ISO 8601) | 是 | 訊息時間戳 |
| `metadata` | JSON string | 否 | 附帶資料（attachment URLs、quick replies 等）|

### 消費者對未知欄位的處理原則

- 消費者必須對未知欄位**寬容處理**（forward compatibility）
- `xreadgroup` 返回的 field-value pairs，未定義的欄位應被忽略，不影響處理流程
- 未知的 `platform` 值應記錄 warn log 後拋棄訊息
- `metadata` 解析失敗時應有 fallback，不阻斷主流程
```

---

## 指數退避重試（Phase 3 新增）

```python
import asyncio
import random

class RetryStrategy:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    async def execute_with_retry(self, func, *args, **kwargs):
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                if self.jitter:
                    delay *= 0.5 + random.random()
                await asyncio.sleep(delay)
```

---

## TDE 加密 + Redis 安全（Phase 3 新增）

```yaml
# PostgreSQL TDE
postgresql:
  encryption:
    algorithm: AES-256
    key_rotation_days: 90
    tde_enabled: true
    ssl_mode: verify-full

# Redis 安全配置
redis:
  tls_enabled: true
  auth:
    requirepass: "${REDIS_PASSWORD}"     # 從密鑰管理器注入
    acl_enabled: true
    default_user_disabled: true
  encryption_at_rest: true
  maxmemory_policy: allkeys-lru
```

---

## 資料庫 Schema Phase 3（增量）

> Phase 1 建立核心表，Phase 2 新增 emotion_history + edge_cases。
> Phase 3 新增以下表。

```sql
-- ============================================================
-- RBAC 權限表（Phase 3 新增）
-- ============================================================
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE role_assignments (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(unified_user_id),
    role_id INTEGER REFERENCES roles(id),
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by UUID REFERENCES users(unified_user_id),
    UNIQUE(user_id, role_id)
);

-- ============================================================
-- PII 稽核日誌（Phase 3 新增）
-- ============================================================
CREATE TABLE pii_audit_log (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    mask_count INTEGER NOT NULL,
    pii_types TEXT[],
    action VARCHAR(20) NOT NULL,
    performed_by UUID REFERENCES users(unified_user_id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pii_audit_date ON pii_audit_log (created_at);

-- ============================================================
-- A/B Testing 實驗（Phase 3 新增）
-- ============================================================
CREATE TABLE experiments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    variants JSONB NOT NULL,
    traffic_split JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'draft'
        CHECK (status IN ('draft', 'running', 'completed', 'aborted')),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ
);

CREATE TABLE experiment_results (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER REFERENCES experiments(id),
    variant VARCHAR(50) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value FLOAT NOT NULL,
    sample_size INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 重試日誌（Phase 3 新增）
-- ============================================================
CREATE TABLE retry_log (
    id SERIAL PRIMARY KEY,
    operation VARCHAR(100) NOT NULL,
    attempt_count INTEGER NOT NULL,
    delay_seconds FLOAT,
    error_message TEXT,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 加密配置（Phase 3 新增）
-- ============================================================
CREATE TABLE encryption_config (
    id SERIAL PRIMARY KEY,
    component VARCHAR(50) NOT NULL,
    encryption_enabled BOOLEAN DEFAULT TRUE,
    algorithm VARCHAR(20) DEFAULT 'AES-256',
    last_key_rotation TIMESTAMPTZ,
    next_key_rotation TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active'
);

-- ============================================================
-- Schema 遷移記錄（Phase 3 新增）
-- ============================================================
CREATE TABLE schema_migrations (
    version VARCHAR(20) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    checksum VARCHAR(64) NOT NULL
);
```

---

## Schema 遷移管理（Phase 3 新增）

```python
# 使用 Alembic 管理所有 Schema 遷移
# 每個 migration 必須有 upgrade() 和 downgrade()

# alembic/versions/001_phase1_core.py
def upgrade():
    """Phase 1 核心表"""
    # users, conversations, messages, knowledge_base,
    # platform_configs, escalation_queue, user_feedback, security_logs

def downgrade():
    # 反向操作

# alembic/versions/002_phase2_intelligence.py
def upgrade():
    """Phase 2 智慧化"""
    # emotion_history, edge_cases, pgvector index

def downgrade():
    # 反向操作

# alembic/versions/003_phase3_enterprise.py
def upgrade():
    """Phase 3 企業級"""
    # roles, role_assignments, pii_audit_log,
    # experiments, experiment_results, retry_log,
    # encryption_config, schema_migrations

def downgrade():
    # 反向操作
```

---

## 部署架構 Phase 3

### Docker Compose（升級版）

```yaml
services:
  omnibot-api:
    build: .
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://omnibot:${DB_PASSWORD}@postgres:5432/omnibot
      - REDIS_URL=rediss://:${REDIS_PASSWORD}@redis:6380/0
      - LLM_API_KEY=${LLM_API_KEY}
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
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
    command: >
      redis-server
        --requirepass ${REDIS_PASSWORD}
        --tls-port 6380
        --tls-cert-file /tls/redis.crt
        --tls-key-file /tls/redis.key
    volumes:
      - ./tls:/tls
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports: ["4317:4317"]

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]

volumes:
  pgdata:
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: omnibot-api
  labels:
    app: omnibot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: omnibot
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  template:
    metadata:
      labels:
        app: omnibot
    spec:
      containers:
        - name: omnibot
          resources:
            requests: { cpu: "500m", memory: "512Mi" }
            limits: { cpu: "2000m", memory: "2Gi" }
          readinessProbe:
            httpGet: { path: /api/v1/health, port: 8000 }
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet: { path: /api/v1/health, port: 8000 }
            initialDelaySeconds: 15
            periodSeconds: 30

---
apiVersion: v1
kind: Service
metadata:
  name: omnibot-api
spec:
  type: LoadBalancer
  selector:
    app: omnibot
  ports:
    - port: 80
      targetPort: 8000
```

### 環境分離

| 環境 | 用途 | LLM 模型 | 資料 |
|------|------|----------|------|
| **development** | 本地開發 | mock / 最便宜模型 | seed data |
| **staging** | 整合測試 | 與 production 相同 | 匿名化 production 子集 |
| **production** | 正式環境 | 正式模型 | 真實資料 |

---

## 災備與 Rollback 策略（Phase 3 新增）

### 備份策略

| 元件 | 策略 | 頻率 | 保留期 |
|------|------|------|--------|
| **PostgreSQL** | pg_basebackup + WAL archiving | 每日全備 + 持續 WAL | 30 天 |
| **Redis** | RDB + AOF | RDB 每小時 / AOF 每秒 | 7 天 |
| **配置** | Git 版控 | 每次變更 | 永久 |

### Rollback 策略

```yaml
rollback_procedures:
  knowledge_update:
    description: 知識庫更新回退
    steps:
      - 知識庫條目使用 version + is_active 軟刪除
      - 回退時將舊版本 is_active = TRUE，新版本 = FALSE
      - 觸發 embedding 重建（如有維度變更）

  model_switch:
    description: LLM 模型切換回退
    steps:
      - 透過 A/B Testing 漸進切換（10% -> 50% -> 100%）
      - 監控 FCR / CSAT 指標
      - 若指標下降超過 5%，自動回退至先前模型

  schema_migration:
    description: Schema 遷移回退
    steps:
      - 使用 Alembic 管理遷移
      - 每個 migration 必須有 downgrade()
      - 先在 staging 驗證 upgrade + downgrade
      - Production 執行前建立快照

  experiment_abort:
    description: A/B 實驗緊急中止
    steps:
      - 將實驗 status 設為 'aborted'
      - 所有流量回到 control variant
      - 記錄中止原因
```

### 降級策略

```yaml
degradation_levels:
  level_1_llm_slow:
    trigger: LLM API p95 > 3s
    action:
      - 啟用回覆快取（相同問題 5 分鐘內回傳快取）
      - 關閉 Layer 3 (LLM 生成)
      - 僅使用 Layer 1 + 2

  level_2_llm_down:
    trigger: LLM API 連續失敗 > 3 次
    action:
      - 完全關閉 LLM 相關功能
      - 僅使用規則匹配 (Layer 1)
      - 無法匹配者自動轉接人工

  level_3_db_slow:
    trigger: PostgreSQL p95 > 2s
    action:
      - 啟用 Redis 唯讀快取
      - 暫停非關鍵寫入（回饋收集、稽核日誌暫存 Redis）
      - 恢復後批次寫入

  level_4_full_outage:
    trigger: 核心服務全部不可用
    action:
      - 回傳靜態維護訊息
      - 所有請求記錄至本地檔案
      - 恢復後重播
```

---

## 負載測試（Phase 3 新增）

```yaml
load_test:
  tool: k6
  target: 2000 TPS

  scenarios:
    smoke:
      description: 基線測試
      vus: 10
      duration: 1m

    load:
      description: 正常負載
      vus: 200
      duration: 10m
      thresholds:
        http_req_duration: ["p(95)<1000"]
        http_req_failed: ["rate<0.01"]

    stress:
      description: 壓力測試
      stages:
        - { duration: 2m, target: 500 }
        - { duration: 5m, target: 2000 }
        - { duration: 2m, target: 3000 }  # 超過目標
        - { duration: 2m, target: 0 }

    spike:
      description: 突發流量
      stages:
        - { duration: 10s, target: 3000 }
        - { duration: 1m, target: 3000 }
        - { duration: 10s, target: 0 }

  test_cases:
    - name: FAQ 查詢（Layer 1）
      weight: 40%
      payload: { message: "退貨政策是什麼？" }

    - name: 語義查詢（Layer 2）
      weight: 30%
      payload: { message: "我上週買的東西想退，但不知道怎麼處理" }

    - name: 複雜查詢（Layer 3）
      weight: 20%
      payload: { message: "我的訂單 #12345 物流顯示已到但我沒收到" }

    - name: 情緒觸發（轉接）
      weight: 10%
      payload: { message: "你們到底在搞什麼！已經第三次了！" }
```

---

## 成本模型（Phase 3 新增）

### LLM API 成本估算

| 層級 | 呼叫頻率 | 平均 Token | 單價估算 | 月成本（10 萬對話）|
|------|----------|-----------|---------|-------------------|
| Layer 1 (規則) | 40% | 0 token | $0 | $0 |
| Layer 2 (RAG) | 40% | ~1500 token/次 | $0.003/次 | $120 |
| Layer 3 (LLM) | 10% | ~3000 token/次 | $0.009/次 | $90 |
| Layer 4 (轉接) | 10% | 0 token | $0 | $0 |
| **合計** | — | — | — | **~$210/月** |

### Embedding 成本

| 項目 | 說明 | 成本 |
|------|------|------|
| 知識庫 embedding | 本地模型（MiniLM），無 API 費用 | $0 |
| 查詢 embedding | 每次查詢 encode，本地執行 | $0 |
| GPU 推理成本 | 視部署規模而定 | 依硬體 |

---

## i18n 擴充指引（Phase 3 新增）

```yaml
# 目前支援範圍聲明
current_scope:
  language: zh-TW (繁體中文)
  pii_patterns: 台灣地區格式
  address_format: 台灣行政區

# 擴充計劃（依業務優先序）
expansion_roadmap:
  phase_1:
    - zh-CN (簡體中文): PII pattern + 地址格式
  phase_2:
    - en: PII pattern (SSN, US phone, US address)
    - ja: PII pattern (マイナンバー, 日本電話)
  phase_3:
    - 多語言 intent detection
    - 多語言情緒分析模型
```

---

## ODD 驗證 SQL Phase 3（增量）

> Phase 1 + Phase 2 SQL 繼續使用。以下為 Phase 3 新增查詢。

```sql
-- 成本效益分析
SELECT
    SUM(resolution_cost) AS total_cost,
    COUNT(CASE WHEN first_contact_resolution THEN 1 END) AS resolved_count,
    ROUND(
        SUM(resolution_cost)
        / NULLIF(COUNT(CASE WHEN first_contact_resolution THEN 1 END), 0), 2
    ) AS cost_per_resolution
FROM conversations
WHERE started_at > NOW() - INTERVAL '30 days'
  AND scope_type = 'in_scope';

-- 月度成本報告
SELECT
    DATE_TRUNC('month', m.created_at) AS month,
    m.knowledge_source,
    COUNT(*) AS query_count,
    CASE m.knowledge_source
        WHEN 'rule' THEN 0
        WHEN 'rag' THEN COUNT(*) * 0.003
        WHEN 'wiki' THEN COUNT(*) * 0.009
        ELSE 0
    END AS estimated_cost_usd
FROM messages m
WHERE m.role = 'assistant'
  AND m.created_at > NOW() - INTERVAL '3 months'
GROUP BY 1, 2
ORDER BY 1 DESC, 4 DESC;

-- PII 稽核摘要
SELECT
    DATE(created_at) AS date,
    SUM(mask_count) AS total_masks,
    COUNT(DISTINCT conversation_id) AS conversations
FROM pii_audit_log
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- RBAC 權限審計
SELECT
    u.unified_user_id,
    r.name AS role,
    ra.assigned_at,
    ra.assigned_by
FROM role_assignments ra
JOIN users u ON ra.user_id = u.unified_user_id
JOIN roles r ON ra.role_id = r.id
WHERE ra.assigned_at > NOW() - INTERVAL '30 days'
ORDER BY ra.assigned_at DESC;

-- A/B 實驗效果
SELECT
    e.name AS experiment_name,
    er.variant,
    er.metric_name,
    er.metric_value,
    er.sample_size
FROM experiment_results er
JOIN experiments e ON er.experiment_id = e.id
WHERE e.status = 'running'
ORDER BY e.name, er.variant;
```

---

## 開發任務 Phase 3

### Phase 3: 企業級 + Production Ready（2-3 週）
- [ ] RBAC 權限定義 + Enforcement 中間件
- [ ] 管理 API 加上 BearerAuth + RBAC 保護
- [ ] A/B Testing 框架（hashlib 確定性分配）
- [ ] OpenTelemetry Tracing
- [ ] Grafana Dashboards
- [ ] 告警規則設定（Prometheus）
- [ ] Redis Streams 異步處理（classmethod factory）
- [ ] 指數退避重試機制
- [ ] TDE 加密 + Redis TLS/AUTH/ACL
- [ ] Docker Compose 升級（+otel+prometheus+grafana）
- [ ] Kubernetes Deployment + Service
- [ ] 備份策略（pg_basebackup + WAL + Redis RDB/AOF）
- [ ] Rollback 策略 + 降級策略
- [ ] 負載測試（k6, 4 場景, 2000 TPS）
- [ ] 成本模型 + 月度報告 SQL
- [ ] Schema 遷移管理（Alembic 3 版本）
- [ ] i18n 擴充指引
- [ ] Phase 3 Schema（8 張新表）
- [ ] Phase 3 ODD SQL 查詢

---

## 驗收標準 Phase 3

| KPI | 目標 | 測試方法 |
|-----|------|----------|
| FCR | >= 90% | ODD SQL 查詢 |
| 可用性 | >= 99.9% | 監控儀表板 |
| p95 延遲 | < 1.0s | k6 壓力測試 |
| 災備復原 | < 5 分鐘 | 演練測試 |
| 錯誤率 | < 1% | Prometheus |
| 成本 | < $500/月 | 成本儀表板 |
| RBAC | 4 角色完整 | 功能測試 |
| A/B 自動化 | >= 95% 準確率 | 統計分析 |

---

## v7.0 完整覆蓋檢查

> 以下表格確認三階段合併後完整覆蓋 v7.0 所有模組。

| v7.0 模組 | Phase 1 | Phase 2 | Phase 3 |
|-----------|---------|---------|---------|
| **UnifiedMessage / UnifiedResponse** | Y | - | - |
| **統一回應格式 ApiResponse / PaginatedResponse** | Y | - | - |
| **Webhook 簽名驗證 TG+LINE** | Y | - | - |
| **Webhook 簽名驗證 Messenger+WhatsApp** | - | Y | - |
| **API 設計（端點 + 錯誤碼）** | Y (基礎) | Y (+LLM_TIMEOUT) | Y (+RBAC 保護) |
| **輸入清理 L2** | Y | - | - |
| **基礎 PII L4** | Y | - | - |
| **PII + Luhn 校驗** | - | Y | - |
| **Rate Limiter** | Y | - | - |
| **規則匹配 Layer 1** | Y | - | - |
| **RAG + RRF Layer 2** | - | Y | - |
| **LLM 生成 Layer 3** | - | Y | - |
| **人工轉接（基礎）** | Y | - | - |
| **人工轉接 + SLA** | - | Y | - |
| **DST 對話狀態機** | - | Y | - |
| **統一情緒模組** | - | Y | - |
| **Prompt Injection L3** | - | Y | - |
| **Grounding Checks L5** | - | Y | - |
| **結構化日誌** | Y | - | - |
| **Prometheus Metrics** | - | Y | - |
| **OpenTelemetry Tracing** | - | - | Y |
| **Grafana + 告警** | - | - | Y |
| **RBAC + Enforcement** | - | - | Y |
| **A/B Testing** | - | - | Y |
| **Redis Streams 異步** | - | - | Y |
| **指數退避重試** | - | - | Y |
| **TDE + Redis 安全** | - | - | Y |
| **Docker Compose** | Y (基礎) | - | Y (完整) |
| **Kubernetes** | - | - | Y |
| **備份 / Rollback / 降級** | - | - | Y |
| **負載測試** | - | - | Y |
| **成本模型** | - | - | Y |
| **Schema 遷移管理** | - | - | Y |
| **i18n 擴充指引** | - | - | Y |
| **黃金數據集指引** | - | Y | - |
| **環境分離** | - | - | Y |
| **SLA 定義** | - | - | Y |
| **CSAT 量化指標** | - | - | Y |

### Schema 表格分布

| Phase | 新增表 | 累計 |
|-------|--------|------|
| Phase 1 | users, conversations, messages, knowledge_base, platform_configs, escalation_queue, user_feedback, security_logs | 8 |
| Phase 2 | emotion_history, edge_cases | 10 |
| Phase 3 | roles, role_assignments, pii_audit_log, experiments, experiment_results, retry_log, encryption_config, schema_migrations | 18 |

### ODD SQL 分布

| Phase | 查詢數 | 內容 |
|-------|--------|------|
| Phase 1 | 3 | FCR、延遲、知識命中 |
| Phase 2 | 6 | CSAT、命中分布%、回饋、SLA、情緒、安全阻擋 |
| Phase 3 | 5 | 成本效益、月度成本、PII 稽核、RBAC 審計、A/B 效果 |
| **合計** | **14** | - |

---

## 完整版本資訊

| 檔案 | Phase | 內容 | 開發時間 |
|------|-------|------|---------|
| `omnibot-phase-1.md` | Phase 1 | MVP 基礎 | 3-4 週 |
| `omnibot-phase-2.md` | Phase 2 | 智慧化 + 安全強化 | 3-4 週 |
| `omnibot-phase-3.md` | Phase 3 | 企業級 + Production Ready | 2-3 週 |

**總開發時間**：8-11 週
**最終目標 FCR**：90%
**最終可用性**：99.9%

---

*Phase: 3*
*文件版本: v7.0*
*最後更新: 2026-04-15*
