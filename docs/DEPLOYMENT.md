# 🚀 OmniBot 部署指南 (Deployment Guide)

本文件詳細說明如何將 OmniBot 部署至不同的環境，從本地開發到生產級 K8s 集群。

---

## 1. 系統環境變數

在部署前，請確保已配置以下環境變數 (建議使用 `.env` 文件或容器環境變數)：

| 變數名 | 說明 | 預設值 / 範例 |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL 連接字串 | `postgresql+asyncpg://user:pass@localhost:5432/db` |
| `REDIS_URL` | Redis 連接字串 | `redis://localhost:6379/0` |
| `OMNIBOT_SECRET_KEY` | RBAC Token 簽名金鑰 (重要) | `your-super-secret-hmac-key` |
| `ENCRYPTION_KEY` | 數據庫靜態加密金鑰 (Fernet) | `32-byte-base64-encoded-key` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API Token | `123456:ABC-DEF...` |
| `LINE_CHANNEL_SECRET` | LINE 渠道金鑰 | `secret-from-line-console` |
| `ALERT_WEBHOOK_URL` | 告警 Webhook 地址 | `https://hooks.slack.com/...` |

---

## 2. Docker Compose 部署 (推薦用於中小型生產)

我們提供了完整的 `docker-compose.yaml`，一鍵啟動所有組件：

```bash
# 1. 克隆倉庫
git clone https://github.com/johnnylugm-tech/omnibot-original.git
cd omnibot-original

# 2. 啟動服務 (含 DB, Redis, API)
docker-compose up -d

# 3. 檢查狀態
docker-compose ps
```

---

## 3. Kubernetes (K8s) 部署 (適用於大規模生產)

K8s 配置位於 `k8s/deployment.yaml`。

### 步驟：
1. **建立 Secret**:
   ```bash
   kubectl create secret generic omnibot-secrets \
     --from-literal=secret-key='YOUR_SECRET' \
     --from-literal=db-url='YOUR_DB_URL'
   ```

2. **部署應用**:
   ```bash
   kubectl apply -f k8s/deployment.yaml
   ```

3. **滾動更新**:
   本項目已配置 `RollingUpdate` 策略 (maxUnavailable: 1, maxSurge: 1)，確保服務不中斷。

---

## 4. 數據庫維護與災備

### 執行備份
OmniBot 內建了自動化備份服務，也可以手動執行：
```bash
bash scripts/backup.sh /path/to/backup.sql
```

### 執行還原
當發生災難時，可以使用還原腳本：
```bash
bash scripts/restore.sh /path/to/backup.sql
```

### 數據遷移 (Alembic)
每次升級代碼後，請執行遷移以同步表結構：
```bash
alembic upgrade head
```

---

## 5. 健康檢查與監控

- **Liveness/Readiness**: `/api/v1/health`
- **Metrics (Prometheus)**: 預設集成在 FastAPI 中，可導出至 Prometheus。
- **Logging**: 所有日誌均為結構化 JSON，建議導出至 ELK 或 Loki。

---
*OmniBot - Production Ready Deployment*
