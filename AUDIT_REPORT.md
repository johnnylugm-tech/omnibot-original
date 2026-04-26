# OmniBot 實作審計報告

**審計日期**：2026-04-26
**審計範圍**：https://github.com/johnnylugm-tech/omnibot-original
**審計維度**：完整性 / 正確性 / 一致性 / 程式碼缺陷 / 測試覆蓋

---

## 一、完整性問題（Phase 2 規格未實作）

### 問題 1：Phase 2 規格承諾 4 平台，實作只有 2 個

| 平台 | 規格狀態 | 實作狀態 |
|------|---------|---------|
| Telegram | Phase 1 | ✅ `/api/v1/webhook/telegram` + `TelegramWebhookVerifier` |
| LINE | Phase 1 | ✅ `/api/v1/webhook/line` + `LineWebhookVerifier` |
| Messenger | Phase 2 | ❌ 無 endpoint，無 verifier |
| WhatsApp | Phase 2 | ❌ 無 endpoint，無 verifier |

**位置**：`app/security/webhook_verifier.py`（僅 2 個 class）；`app/api/__init__.py`（僅 2 個 webhook 路由）

**規格依據**：`omnibot-phase-2.md` 第 11 行：「目標：80% FCR + 完整安全層 + **4 平台**」

---

### 問題 2：EmotionTracker 和 DSTManager 存在但從未在 API 中呼叫

**規格要求**（`omnibot-phase-2.md`）：
- `EmotionTracker` 需每則訊息呼叫 `add()`，連續 3 次負面情緒觸發轉接
- `DSTManager.process_turn()` 需在每次對話輪次呼叫以更新對話狀態

**實作現況**：
```python
# app/api/__init__.py 第 24-36 行
from app.services.dst import DSTManager       # ✅ import 了
from app.services.emotion import EmotionTracker  # ✅ import 了

dst_manager = DSTManager()                   # ✅ 初始化了
# ... 但從未呼叫 dst_manager.process_turn(...)
# ... 從未呼叫 emotion_tracker.add(...)
```

`HybridKnowledgeV7` 也從未接收包含 emotion/sentiment 的 `user_context`，DST 狀態在整個 API 生命週期中從未被更新過。

---

### 問題 3：`emotion_history` 和 `edge_cases` 表有 Schema 定義但無 ORM Model

**規格依據**：`omnibot-phase-2.md` 第 760-783 行

| 表名 | Schema 有定義 | ORM Model 有 | SCHEMA_SQL 有 |
|------|:---:|:---:|:---:|
| `emotion_history` | ✅ | ❌ | ❌ |
| `edge_cases` | ✅ | ❌ | ❌ |

**位置**：`app/models/database.py`（14 個 ORM Model 中不包含這兩者）

---

## 二、正確性問題（邏輯錯誤）

### 問題 4：Layer 3 LLM 生成層為 stub，但規格聲稱已實作

**規格聲明**：`omnibot-phase-2.md` 第 1100 行（v7.0 覆蓋檢查表）
```
| **LLM 生成 Layer 3** | - | Y | - |
```

**實作**：`app/services/knowledge.py` 第 106-108 行
```python
async def _llm_generate(self, query: str, context: dict) -> Optional[KnowledgeResult]:
    """LLM response generation (Placeholder)"""
    return None
```

`HybridKnowledgeV7.__init__` 接受 `llm_client=None`，Layer 3 分支永遠 fallback 至 Layer 4 轉接。

---

### 問題 5：Telegram webhook 端點未建立 Conversation 記錄

**規格依據**：`omnibot-phase-1.md` 第 642 行 Schema定義：`messages.conversation_id REFERENCES conversations(id)`（非 NULL）

**實作**：`app/api/__init__.py` 第 121-163 行
```python
db.add(Message(role="user", content=processed_text))
db.add(Message(role="assistant", content=response_content, knowledge_source=knowledge_source))
await db.commit()
# 沒有 Conversation 的 INSERT
# Message.conversation_id 實際為 NULL
```

所有 DST 功能（Phase 2）依賴 `conversation_id` 追蹤對話狀態，但 conversation 記錄從未建立。

---

## 三、一致性問題（文件與實作或文件間衝突）

### 問題 6：Phase 1 FCR 50% 目標與 Phase 2 Layer 1 40% 貢獻矛盾

| 文件 | 內容 |
|------|------|
| `omnibot-phase-1.md:28` | 「FCR 50%，FCR **僅計算 Layer 1** 成功回覆的案件」 |
| `omnibot-phase-2.md:31` | 「Layer 1 規則匹配 ... **預期貢獻 40%**」 |

Layer 1 自己貢獻 40%，但 Phase 1 要求 Layer 1 alone 達成 50%。兩數字無法同時成立。

---

### 問題 7：EscalationManager 規格升級但實作仍是 BasicEscalationManager

**規格**：`omnibot-phase-2.md:464` — Phase 2 升級為 `EscalationManager`（含 SLA 分級與追蹤）

**實作**：`app/services/escalation.py`
```python
class BasicEscalationManager:  # ← 仍是 Phase 1 的
    """Phase 1: Basic escalation, no SLA tracking"""
    def create(self, request: EscalationRequest) -> int:
        return 1  # 硬返回，沒寫資料庫
    def assign(self, escalation_id: int, agent_id: str) -> None:
        pass     # 空殼
    def resolve(self, escalation_id: int) -> None:
        pass     # 空殼
```

SLA 追蹤（normal 30min / high 15min / urgent 5min）完全不存在，`escalation_queue.sla_deadline` 欄位從未填充。

---

## 四、程式碼缺陷

### 問題 8：`emotion_history` ORM Model 缺失，但情緒模組依賴持久化

- `EmotionTracker` 依賴「歷史記錄」計算半衰期衰減
- Phase 2 規格要求：每則情緒事件寫入 `emotion_history` 表
- 實際：`EmotionTracker` 的 `history: List[EmotionScore]` 是記憶體內 list，程序重啟後資料流失
- Phase 2 ODD SQL（第 867-876 行）有查詢 `emotion_history` 的語句，但該表不存在

---

### 問題 9：`schema_migrations` 表有 Schema 定義但無 ORM Model

**規格**：`omnibot-phase-3.md` 第 617-622 行

```sql
CREATE TABLE schema_migrations (
    version VARCHAR(20) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    checksum VARCHAR(64) NOT NULL
);
```

- `app/models/database.py` 中無對應 ORM Model
- Alembic 遷移框架目錄（`alembic/versions/`）完全不存在
- Phase 3 開發任務（第 1061 項）「Schema 遷移管理（Alembic 3 版本）」未完成

---

## 五、測試覆蓋問題

### 問題 10：Phase 2 關鍵功能無單元測試

| 功能 | 實作檔案 | 測試存在 |
|------|---------|:---:|
| `EmotionTracker.current_weighted_score()`（半衰期衰減） | `app/services/emotion.py` | ❌ |
| `EmotionTracker.should_escalate()`（連續 3 次負面） | `app/services/emotion.py` | ❌ |
| `DSTManager.process_turn()`（狀態機轉移） | `app/services/dst.py` | ❌ |
| `ABTestManager.get_variant()`（確定性分流） | `app/services/ab_test.py` | ✅ |
| `PromptInjectionDefense.build_sandwich_prompt()` | `app/security/prompt_injection.py` | ❌ |
| Grounding Checker | 規格有，實作無 | N/A |

---

## 六、已排除項目

以下項目經查證後不構成問題：

| 懷疑的問題 | 結論 |
|-----------|------|
| RateLimiter `_tokens=0` 初始值會擋第一個請求 | ❌ 排除：`__post_init__` 正確設回 `capacity` |
| Phase 3 完全沒實作 | ❌ 排除：RBAC、ABTest、RetryStrategy、AsyncMessageProcessor、OpenTelemetry 均有實作 |
| webhook_verifier import 語法錯誤 | ❌ 排除：實作使用 `from app.models import`，規格文件寫 `from phase1 import`，是規格文件問題，非實作問題 |

---

## 七、摘要

| 類型 | 問題數 | 最高優先 |
|------|:---:|------|
| **完整性** | 3 | Messenger/WhatsApp 未實作；Emotion/DST 未接入 API |
| **正確性** | 2 | LLM Layer 3 stub；Conversation 記錄從未建立 |
| **一致性** | 2 | Layer 1 貢獻 40% vs 50% 矛盾；BasicEscalationManager 冒充升級版 |
| **程式碼缺陷** | 2 | emotion_history ORM 缺失；Alembic 遷移完全未建立 |
| **測試覆蓋** | 1 | Phase 2 關鍵功能大面積無測試 |

**合計：10 個具體問題**

---

## 八、根本原因分析

1. **規格與實作脫鉤**：`omnibot-phase-2.md` v7.0 覆蓋表標記「LLM Layer 3 為 Y」，DELIVERY_REPORT 聲稱「100% 一致」，但實作為 stub。三個地方對同一件事的描述互相矛盾，且沒有人對齊。
2. **增量式實作但不完整**：Phase 2 新增了 `emotion.py` 和 `dst.py` 檔案，但 API 端點從未呼叫這些模組，形成「有實作檔案但系統整體不工作」的狀態。
3. **規格書本身錯誤**：Phase 1 FCR 50% 和 Phase 2 Layer 1 40% 的矛盾存在於規格文件之間，即使實作完全正確，規格本身也有問題。
