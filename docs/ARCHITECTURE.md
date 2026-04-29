# 🏗 OmniBot 技術架構 (System Architecture)

OmniBot 採用分層防禦與混合檢索架構，旨在平衡回應速度、內容質量與系統安全性。

---

## 1. 五層智慧知識管線 (V7 Hybrid Layer)

當一條消息進入系統後，會依序通過以下五層過濾與檢索：

### Layer 1: 規則引擎 (Rule-based)
- **技術**: 正則表達式與關鍵字精確匹配。
- **目的**: 處理 FAQ、問候語或特定業務指令，確保 100% 準確率。
- **出口**: 若信心度 > 0.9，直接返回結果。

### Layer 2: RAG 檢索 (Retrieval-Augmented Generation)
- **技術**: PostgreSQL `pgvector` + `SentenceTransformer` (paraphrase-multilingual-MiniLM-L12-v2)。
- **目的**: 透過語義相似度尋找最接近的知識庫文檔。
- **Fusion**: 使用 RRF (Reciprocal Rank Fusion) 整合規則與向量結果。

### Layer 3: LLM 生成 (Generative AI)
- **技術**: 整合 OpenAI / Anthropic / Gemini。
- **目的**: 當知識庫無直接答案時，根據檢索到的片段生成人類語感的回答。

### Layer 4: 人工轉接 (Human Escalation)
- **觸發條件**:
  - 檢測到強烈負面情緒。
  - 觸發 PII 敏感資訊（出於合規考慮不使用 LLM 回覆）。
  - 下游層級無法提供高信心度回答。

### Layer 5: 向量 Grounding (Fact-Checking)
- **技術**: 餘弦相似度 (Cosine Similarity)。
- **目的**: 將 Layer 3 生成的回答與 Layer 2 檢索到的原文進行交叉比對。若相似度 < 0.75，則判定為幻覺並攔截。

---

## 2. 安全防護架構

### RBAC 2.0 (Role-Based Access Control)
- **機制**: HMAC-SHA256 簽名。
- **流程**: API 請求攜帶 `Authorization: Bearer <JWT>` -> Enforcer 校驗簽名 -> 查驗權限矩陣。

### PII 脫敏流水線
1. **正規化**: 去除特殊符號與空格。
2. **正則匹配**: 識別信用卡、身分證、手機等模式。
3. **算法驗證**: 對於信用卡執行 Luhn 算法驗證，排除誤報。
4. **動態遮蔽**: 根據配置執行 `****` 替換。

---

## 3. 可觀測性與自癒機制

- **KPI Manager**: 實時從 PostgreSQL 聚合統計數據。
- **Degradation Manager**: 監控 P95 延遲與 Error Rate。當 LLM 延遲 > 3s 時自動降級至 Level 1。
- **Async Worker**: 基於 Redis Streams 處理非同步分析與日誌。

---
*OmniBot - Architected for Trust and Speed*
