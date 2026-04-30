# OmniBot Spec Audit Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 spec-audit 發現的 4 個實質問題（2 個 spec bug、1 個 spec gap、1 個 checklist gap），其餘 7 個 finding 已確認無需修正。

**Architecture:** 純文件修改，無需接觸程式碼。四項修改分布於 Phase 2 spec、Phase 3 spec、Phase 1 checklist 三個 markdown 檔案。

**Tech Stack:** Markdown 編輯（無特殊工具需求）

---

## Impact Summary（不需修改的 7 個 finding）

以下 7 個 finding 已確認 spec 內容正確，無需任何修改：

| Finding | 結論 |
|---|---|
| C3: AsyncMessageProcessor 起源 Phase 3 | ✓ SPEC 正確 — Phase 2 spec 末尾有獨立備註明確說明 |
| C4: Phase 2 dev tasks 無 Redis/Retry | ✓ SPEC 正確 — Phase 2 dev tasks 清單確認不包含 |
| M1: 8 個錯誤碼總數 | ✓ SPEC 正確 — Phase 1:5 + Phase 2:1 + Phase 3:2 = 8 |
| M2: ODD SQL knowledge_source 值 | ✓ SPEC 正確 — Phase 2 ODD SQL 確實使用 rule/rag/wiki/escalate |
| M3: Degradation yaml 與 checklist 對應 | ✓ SPEC 正確 — 4 個 level 觸發條件全部有對應測試 |
| M4: Phase 1 conversations API 定義 | ✓ SPEC 正確 — Phase 1 spec 確實定義了 platform + time range |
| M6: G-05 Redis Streams schema | ✓ SPEC 已填補 — Phase 3 spec 有完整訊息 payload schema |

---

## File Map

| 檔案 | 修改類型 |
|---|---|
| `SPEC/omnibot-phase-2-design.md` | Bug fix (C1, M5) |
| `SPEC/omnibot-phase-3-design.md` | Bug fix (C2) |
| `SPEC/omnibot-tdd-verification-checklist.md` | Gap fix (C5) |

---

## Task 1: 修正 Phase 2 spec — HybridKnowledgeLayer `_llm_generate` source 值（C1）

**Files:**
- Modify: `SPEC/omnibot-phase-2-design.md`

**Objective:** Phase 2 spec HybridKnowledgeLayer `_llm_generate` 回傳 `source="wiki"` 為錯誤，應為 `source="llm"`（因為 LLM 生成的內容不應標記為 wiki 來源）。

**Change:** 在 Phase 2 spec 中找到以下程式碼區塊（位置約在 Layer 3: LLM 生成章節），將 `source="wiki"` 改為 `source="llm"`：

```python
        result = self._llm_generate(query, user_context)
        if result is not None:
            return KnowledgeResult(
                id=0,
                content=result.content,
                confidence=result.confidence,
                source="llm",  # ← 修正：LLM 生成內容應標記為 llm，非 wiki
            )
```

- [ ] **Step 1: 確認 Phase 2 spec 中的目標位置**

使用 search_files 在 `SPEC/omnibot-phase-2-design.md` 中搜尋 `source="wiki"` 確認行號。

Run: `grep -n 'source="wiki"' SPEC/omnibot-phase-2-design.md`
Expected: 找到包含 `_llm_generate` 的段落，確認這是 Layer 3 LLM 生成程式碼區塊

- [ ] **Step 2: 修正 source 值**

使用 patch 將 Phase 2 spec 中的 `source="wiki"` 改為 `source="llm"`（注意：只改 `_llm_generate` 回傳的該處，不改其他地方的 wiki 引用）。

patch 引用的 old_string（完整區塊）:
```
        result = self._llm_generate(query, user_context)
        if result is not None:
            return KnowledgeResult(
                id=0,
                content=result.content,
                confidence=result.confidence,
                source="wiki",
            )
```

- [ ] **Step 3: 驗證修正**

搜尋 Phase 2 spec 確認 `_llm_generate` 段落已改為 `source="llm"`，且其餘 `wiki` 來源標記（Layer 2 RAG 回傳）未被更動。

- [ ] **Step 4: Commit**

```bash
git add SPEC/omnibot-phase-2-design.md
git commit -m "fix(spec): HybridKnowledgeLayer _llm_generate source label 'wiki' → 'llm'"
```

---

## Task 2: 修正 Phase 3 spec — ODD SQL 合計數學錯誤（C2）

**Files:**
- Modify: `SPEC/omnibot-phase-3-design.md`

**Objective:** Phase 3 spec 標頭聲明 ODD SQL 合計 13 支，實際為 14 支（Phase 1:3 + Phase 2:6 + Phase 3:5 = 14）。

**Change:** 將 Phase 3 spec 中 ODD SQL 總表標頭列的 `**合計** | **13**` 改為 `**合計** | **14**`。

- [ ] **Step 1: 確認目標位置**

搜尋 Phase 3 spec 中 ODD SQL 總表（`合計` + `13`）。

Run: `grep -n "合計" SPEC/omnibot-phase-3-design.md`
Expected: 找到 ODD SQL 總結表格的合計列，確認周圍有 Phase 1/2/3 數量

- [ ] **Step 2: 修正合計數**

patch old_string:
```
| Phase 1 | 3 | FCR、延遲、知識命中 |
| Phase 2 | 6 | CSAT、命中分布%、回饋、SLA、情緒、安全阻擋 |
| Phase 3 | 5 | 成本效益、月度成本、PII 稽核、RBAC 審計、A/B 效果 |
| **合計** | **13** | - |
```

new_string:
```
| Phase 1 | 3 | FCR、延遲、知識命中 |
| Phase 2 | 6 | CSAT、命中分布%、回饋、SLA、情緒、安全阻擋 |
| Phase 3 | 5 | 成本效益、月度成本、PII 稽核、RBAC 審計、A/B 效果 |
| **合計** | **14** | - |
```

- [ ] **Step 3: 驗證修正**

確認 Phase 3 spec 中合計已改為 14。

- [ ] **Step 4: Commit**

```bash
git add SPEC/omnibot-phase-3-design.md
git commit -m "fix(spec): correct ODD SQL total count 13 → 14 in Phase 3 spec"
```

---

## Task 3: 填補 Phase 2 spec — RetryStrategy class 原始碼區塊（M5）

**Files:**
- Modify: `SPEC/omnibot-phase-2-design.md`

**Objective:** Phase 3 dev tasks 列出「指數退避重試機制」，但 Phase 2 spec 缺乏對應的 `RetryStrategy` class 原始碼定義，屬於 spec 不完整。需在 Phase 2 spec 中補充 `RetryStrategy` class 原始碼。

**Change:** 在 Phase 2 spec 的「Phase 2: 智慧化 + 安全強化」開發任務區塊之後、或在架構設計章節中新增 `RetryStrategy` class 原始碼區塊。

原始碼應包含：
- `RetryStrategy` class with `max_retries`, `base_delay`, `max_delay`, `jitter` 參數
- `exponential_backoff` method 實作
- 說明此為 Phase 3 Redis Streams 重試機制的基礎

```python
class RetryStrategy:
    """指數退避重試策略。

    用於 Phase 3 Redis Streams 訊息處理中的 API 呼叫重試。
    Phase 2 預先定義此 class，Phase 3 再與 AsyncMessageProcessor 整合。

    Attributes:
        max_retries: 最大重試次數
        base_delay: 初始延遲秒數（預設 1.0s）
        max_delay: 最大延遲秒數上限（預設 30.0s）
        jitter: 是否加入隨機 jitter（預設 True，防止 thundering herd）
    """

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

    def exponential_backoff(self, attempt: int) -> float:
        """計算第 attempt 次重試的延遲秒數。

        Args:
            attempt: 由 0 開始的重試次數（0 = 第一次重試）

        Returns:
            等待秒數，符合指數退避曲線
        """
        import random

        delay = self.base_delay * (2**attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay *= random.uniform(0.5, 1.5)
        return delay

    def should_retry(self, attempt: int) -> bool:
        """判斷是否應該繼續重試。

        Args:
            attempt: 目前已嘗試次數（不含原始呼叫）

        Returns:
            True if 仍有重試次數，False if 已達上限
        """
        return attempt < self.max_retries
```

- [ ] **Step 1: 確認 Phase 2 spec 中新增 class 的位置**

搜尋 Phase 2 spec 結尾或「架構設計」章節，確認 Phase 3 新增項目（如 `AsyncMessageProcessor` 起源備註）之前的位置。

Run: `grep -n "Phase 3\|AsyncMessageProcessor\|指數退避\|Redis Streams" SPEC/omnibot-phase-2-design.md`
Expected: 找到 Phase 3 備註段落，在其之前新增 RetryStrategy 區塊

- [ ] **Step 2: 在 Phase 2 spec 新增 RetryStrategy 原始碼區塊**

在 Phase 3 備註段落之前新增章節：

```
## 指數退避重試（Phase 3 前置定義）

（上方為 class 原始碼）
```

- [ ] **Step 3: 驗證新增內容**

確認 Phase 2 spec 現在包含完整的 `RetryStrategy` class定義。

- [ ] **Step 4: Commit**

```bash
git add SPEC/omnibot-phase-2-design.md
git commit -m "feat(spec): add RetryStrategy class definition to Phase 2 spec"
```

---

## Task 4: 填補 Phase 1 checklist — Health check `unhealthy` 狀態測試（C5）

**Files:**
- Modify: `SPEC/omnibot-tdd-verification-checklist.md`

**Objective:** Phase 1 spec 定義 health API 的 `status` enum 包含 `unhealthy`，但 Phase 1 checklist 只有 `degraded` 測試，缺少 `unhealthy` 狀態的對應測試。

**Change:** 在 Phase 1 checklist 的「Health Check」章節中新增 `unhealthy` 狀態測試：

```
- [ ] test_health_check_status_unhealthy_when_service_down
```

具體測試行為：
- Mock 三個依賴服務（Redis、PostgreSQL、LLM API）全部無法連接
- 呼叫 `GET /health`
- 預期 `status` 為 `"unhealthy"`、`healthy_components` 陣列中無任何成員、`degraded_components` 為空

- [ ] **Step 1: 確認 Phase 1 checklist 中 health check 章節位置**

搜尋 Phase 1 checklist 中包含 `test_health_check` 的位置。

Run: `grep -n "test_health_check\|## Health" SPEC/omnibot-tdd-verification-checklist.md | head -20`
Expected: 找到 Phase 1 health check 測試章節（test_health_check_returns_200 和 test_health_check_degraded）

- [ ] **Step 2: 新增 unhealthy 測試**

在 `test_health_check_degraded` 測試之後、新增 Phase 2 測試之前，新增 unhealthy 測試。

old_string:
```
- [ ] test_health_check_degraded_when_redis_down
```

new_string:
```
- [ ] test_health_check_degraded_when_redis_down
- [ ] test_health_check_status_unhealthy_when_service_down
```

- [ ] **Step 3: 驗證 Phase 1 spec 的 unhealthy 定義**

再次確認 Phase 1 spec health endpoint schema 定義了 `unhealthy` enum 值（已於 audit 中驗證）。

- [ ] **Step 4: Commit**

```bash
git add SPEC/omnibot-tdd-verification-checklist.md
git commit -m "feat(checklist): add Phase 1 health check unhealthy status test"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** 確認 4 個 task 對應 4 個需要修正的 finding，無遺漏
- [ ] **Placeholder scan:** 確認無 "TBD"、"TODO"、"類似於" 等未定義內容
- [ ] **Type consistency:** 所有程式碼區塊的 class/method 名稱與 spec 原文一致
- [ ] **Commit messages:** 每個 task 有獨立 commit，message 清晰描述變更

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/2026-04-30-omnibot-spec-audit-fix.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
