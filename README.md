# 🤖 OmniBot: Ultimate Enterprise Bot Backend

OmniBot 是一款專為企業級需求設計的多平台機器人後端服務。它結合了規則引擎、RAG (檢索增強生成) 與大型語言模型 (LLM)，並具備極高的安全防護與可觀測性標準。

[![SSI Score](https://img.shields.io/badge/SSI_Score-100%2F100-brightgreen)](SPEC/omnibot-tdd-verification-report.md)
[![TDD Coverage](https://img.shields.io/badge/TDD_Pass_Rate-100%25-blue)](SPEC/omnibot-tdd-verification-report.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌟 核心亮點

### 1. 五層智慧知識管線 (V7 Hybrid Layer)
OmniBot 採用業界領先的混合檢索架構，確保回應的準確性與安全性：
- **Layer 1: 規則匹配** - 高精確度、即時響應。
- **Layer 2: RAG 檢索** - 基於 pgvector 的語義相似度搜索。
- **Layer 3: LLM 生成** - 針對複雜情境的動態生成。
- **Layer 4: 人工轉接** - 自動識別情緒或 PII，無縫銜接真人客服。
- **Layer 5: 向量 Grounding** - 即時檢測並攔截 LLM 幻覺。

### 2. 生產級安全防護
- **RBAC 2.0**: 基於 HMAC-SHA256 簽名的安全 Bearer Token。
- **PII 脫敏**: 自動遮蔽信用卡 (Luhn 驗證)、身分證、電話等敏感資訊。
- **紅隊防禦**: 內建對抗 Prompt Injection 與越權攻擊的防護邏輯。
- **數據加密**: 敏感內容在數據庫中進行 AES-256 加密。

### 3. 全方位可觀測性
- **KPI 儀表板**: 自動統計 FCR、SLA 合規率、平均響應時間等 12+ 維度。
- **非同步告警**: 異常錯誤率或 SLA 逾期時，自動觸發 Webhook 告警。
- **分散式追蹤**: 內建 OpenTelemetry 支援，追蹤每一筆 Request 的流向。

---

## 🚀 快速開始

### 環境需求
- Python 3.9+
- PostgreSQL (含 pgvector 擴充)
- Redis

### 快速執行 (Docker)
```bash
docker-compose up -d
```

### 開發者模式
```bash
# 安裝依賴
pip install -r requirements.txt

# 初始化數據庫
alembic upgrade head

# 啟動 API (預設 8000 端口)
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

---

## 📚 相關文件

- [**部署指南 (Deployment Guide)**](docs/DEPLOYMENT.md) - 如何在生產環境、Docker 或 K8s 中部署。
- [**使用者手冊 (User Manual)**](docs/USER_MANUAL.md) - 包含 API 調用、認證流程與管理介面說明。
- [**開發架構 (Architecture)**](docs/ARCHITECTURE.md) - 深入了解 5 層檢索管線與系統組件。
- [**驗證報告 (TDD Report)**](SPEC/omnibot-tdd-verification-report.md) - 最新的測試數據與規格合規證明。

---

## 🛠 工程卓越

OmniBot 堅持嚴格的工程標準：
- **100% Type Safe**: 通過 `mypy --disallow-untyped-defs` 驗證。
- **Atomic TDD**: 645+ 測試案例，涵蓋所有業務邊界、邊緣情況與安全漏洞。
- **Modern API**: 全面採用 FastAPI `lifespan` 模式與非同步驅動。

---
© 2026 OmniBot Team. Licensed under MIT.
