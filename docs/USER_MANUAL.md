# 📖 OmniBot 使用者手冊 (User Manual)

歡迎使用 OmniBot。本手冊將引導您如何管理知識庫、調用 API 以及理解系統的防護機制。

---

## 1. 認證流程 (Authentication)

OmniBot 所有受保護的 API 均需要 Bearer Token 認證。

### 如何獲取 Token
在生產環境中，Token 由認證中心分發。Token 格式為：`{payload_b64}.{signature_hmac256}`。

### 如何使用
在 HTTP Header 中加入：
```http
Authorization: Bearer <YOUR_TOKEN>
```

---

## 2. 知識庫管理 (Knowledge Management)

OmniBot 提供完整的 CRUD 介面來管理機器人的「大腦」。

### 查詢知識
- **Endpoint**: `GET /api/v1/knowledge`
- **參數**: `q` (關鍵字), `category` (分類)
- **範例**: `GET /api/v1/knowledge?q=開戶&category=銀行業務`

### 新增知識
- **Endpoint**: `POST /api/v1/knowledge`
- **Body**:
  ```json
  {
    "category": "FAQ",
    "question": "如何重設密碼？",
    "answer": "您可以點選登入頁面的「忘記密碼」按鈕。",
    "keywords": ["密碼", "重設", "忘記"]
  }
  ```

---

## 3. 自動防護機制說明

### PII 遮蔽 (PII Masking)
當使用者發送包含敏感資訊的消息時，OmniBot 會自動執行遮蔽。
- **身分證字號**: `A123****89`
- **信用卡號**: `4524-****-****-1234` (通過 Luhn 驗證)
- **手機號碼**: `0912***456`

### 幻覺攔截 (Hallucination Detection)
若 LLM 生成的內容與知識庫事實不符（相似度 < 0.75），系統會自動攔截該回答並轉接人工客服，確保企業回覆的權威性。

### 服務降級 (Resilience)
當系統檢測到 LLM 延遲過高或數據庫壓力大時，會自動切換模式：
- **Level 1**: 停用 LLM 生成，僅使用規則匹配與 RAG。
- **Level 2**: 停用 RAG，僅使用靜態規則。
- **Level 3**: 維護模式。

---

## 4. 業務 KPI 監控

管理員可以通過 `KPIManager` 獲取以下核心數據：
- **FCR (一次性解決率)**: 衡量機器人是否能直接解決問題。
- **SLA 合規率**: 衡量人工轉接後的處理速度是否達標。
- **情感分佈**: 監控使用者負面情緒比例，預防公關危機。

---

## 5. 常見問題 (FAQ)

**Q: 為什麼我調用 API 回傳 403 Forbidden？**
A: 請檢查您的 Token 權限。某些 API（如刪除知識）需要 `admin` 角色。

**Q: 機器人回答「正在轉接人工」的原因有哪些？**
A: 1. 檢測到負面情緒；2. 觸發了 PII 敏感資訊；3. LLM 幻覺檢測未通過；4. 問題超出知識庫範圍。

---
*OmniBot - Empowering Conversational Intelligence*
