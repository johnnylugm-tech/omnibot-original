# OmniBot Phase 1

基於 FastAPI 構建的多平台機器人後端服務。

## 🚀 核心功能
- **多平台 Webhook 支援**: 已整合 Telegram 與 LINE Webhook。
- **安全防護**:
  - PII 遮罩處理 (電話、Email、地址)。
  - 令牌桶 (Token Bucket) 速率限制。
  - Webhook 簽章驗證基礎架構。
- **知識庫介接**: 結構化問答查詢與管理介面。

## 🛠 工程標準
本專案已通過 Harness Quality Framework 的品質驗證 (得分: 87.56)。
- **測試**: 使用 Pytest，目前覆蓋率 > 90%。
- **型別安全**: 嚴格遵守 Mypy 靜態型別檢查。
- **規範**: 使用 Ruff 進行程式碼風格檢查與自動格式化。

## 📦 安裝與執行
1. 安裝依賴:
   ```bash
   pip install -r requirements.txt
   ```
2. 執行測試:
   ```bash
   pytest --cov=app
   ```
3. 啟動服務:
   ```bash
   uvicorn app.api:app --reload
   ```
