# OmniBot Phase Web — TDD 驗證清單

**依據**：`SPEC/omnibot-phase-web.md` v1.0  
**覆蓋範圍**：Phase Web 所有功能 100% 拆解  
**檔案狀態**：TDD 驅動開發用，先列測試案例再實作

---

## 測試驅動開發口號

> **Red — Green — Refactor**：每個條目先列測試案例（Red），實作後通過（Green），重構後保持通過（Refactor）。

---

## 領域 1：JWT / Token 管理

### TokenManager.create_access_token()

- [ ] **T1.1** `create_access_token(user_id, session_id, role)` 回傳非空 JWT 字串
- [ ] **T1.2** JWT payload 包含 `sub`（user_id）、`sid`（session_id）、`role`、`type="access"`、`jti`
- [ ] **T1.3** JWT `exp` 為目前時間 + ACCESS_TOKEN_EXPIRE_MINUTES（15 分鐘）
- [ ] **T1.4** 兩個相同參數的呼叫產生不同的 `jti`（UUID uniqueness）

### TokenManager.create_refresh_token()

- [ ] **T1.5** `create_refresh_token(user_id, session_id)` 回傳非空 JWT 字串
- [ ] **T1.6** JWT payload 包含 `sub`、`sid`、`type="refresh"`、`jti`
- [ ] **T1.7** JWT `exp` 為目前時間 + REFRESH_TOKEN_EXPIRE_DAYS（30 天）
- [ ] **T1.8** access token 和 refresh token 長度差異明顯（payload 結構不同）

### TokenManager.verify_access_token()

- [ ] **T1.9** 有效 access token 驗證通过，回傳完整 payload
- [ ] **T1.10** 過期 access token 拋出 `HTTPException(status_code=4401)` detail="Token expired"
- [ ] **T1.11** 格式錯誤的 token 拋出 `HTTPException(status_code=4401)` detail="Invalid token"
- [ ] **T1.12** refresh token 當作 access token 送入，拋出 `HTTPException(status_code=4401)` detail="Not an access token"

### TokenManager.verify_refresh_token()

- [ ] **T1.13** 有效 refresh token 驗證通过，回傳 payload
- [ ] **T1.14** access token 當作 refresh token 送入，拋出 `HTTPException(status_code=4401)` detail="Not a refresh token"
- [ ] **T1.15** 過期 refresh token 拋出 `HTTPException(status_code=4401)` detail="Token expired"

### TokenManager.get_user_from_payload()

- [ ] **T1.16** payload 轉換為 `WebUser`，包含正確 `user_id`、`session_id`、`role`
- [ ] **T1.17** 缺少 role 的 payload 回傳預設值 `role="web_user"`

### Refresh Token Rotation

- [ ] **T1.18** `POST /auth/refresh` 後，舊 refresh token 的 `session_id` 在 `web_sessions` 中狀態為 `revoked_at != NULL`
- [ ] **T1.19** 使用已撤銷的 refresh token 再次呼叫 refresh，拋出 `HTTPException(4401)` detail="Token reuse detected"
- [ ] **T1.20** Token reuse 發生時，`revoke_all_user_sessions` 撤銷該 user 的所有 session
- [ ] **T1.21** Rotation 完成後，新 refresh token 和新 session_id 對應

---

## 領域 2：密碼雜湊

### 雜湊與驗證

- [ ] **T2.1** `hash_password("password123")` 回傳以 `$argon2id$` 開頭的字串
- [ ] **T2.2** `verify_password("password123", hash)` 回傳 `True`
- [ ] **T2.3** `verify_password("wrongpassword", hash)` 回傳 `False`
- [ ] **T2.4** 連續 3 次 `verify_password` 錯誤密碼，驗證時間波動在安全範圍內（無時序攻擊）
- [ ] **T2.5** `hash_password` 每次呼叫產生不同的 salt（同一密碼兩次雜湊結果不同）

---

## 領域 3：WebAuthMiddleware

### 公開端點繞過

- [ ] **T3.1** `GET /api/v1/auth/login` 不攜帶 token → 200（不通過驗證）
- [ ] **T3.2** `GET /api/v1/auth/register` 不攜帶 token → 200
- [ ] **T3.3** `GET /api/v1/auth/refresh` 不攜帶 token → 200（從 cookie 取 refresh_token）
- [ ] **T3.4** `GET /api/v1/auth/verify-email` 不攜帶 token → 200
- [ ] **T3.5** `GET /ws/chat` 不攜帶 token → 200（WebSocket 單獨處理 handshake）
- [ ] **T3.6** `GET /api/v1/health` 不攜帶 token → 200

### Token 提取

- [ ] **T3.7** `Authorization: Bearer <token>` header 可正確提取 token
- [ ] **T3.8** `?token=<token>` query parameter 可正確提取 token（WebSocket handshake）
- [ ] **T3.9** 同時有 header 和 query token 時，header 優先

### JWT 驗證失敗

- [ ] **T3.10** `GET /api/v1/auth/me` 帶無效 token → 401 "Missing token" 或 "Invalid token"
- [ ] **T3.11** Session 在 Redis 中 `revoked_at != NULL` → 401 "Session revoked"

### 有效驗證

- [ ] **T3.12** 有效 JWT + 未撤銷 session → `request.state.web_user` 正確附加 `WebUser`
- [ ] **T3.13** 跨請求：每個 request 都重新驗證 JWT 和 session（無狀態）

---

## 領域 4：認證端點

### POST /api/v1/auth/register

- [ ] **T4.1** 提供合法 email + password → 201，回傳 `{user_id, email}`
- [ ] **T4.2** email 已存在 → 409 "Email already registered"
- [ ] **T4.3** 密碼以 argon2id 格式寫入資料庫（不儲存明文）
- [ ] **T4.4** users 表中 `platform='web'`、`role='web_user'`
- [ ] **T4.5** 密碼長度 < 8 字元 → 422 validation error
- [ ] **T4.6** 無效 email 格式 → 422 validation error

### POST /api/v1/auth/login

- [ ] **T4.7** 正確帳密 → 200，回傳 `access_token`、`refresh_token`、`expires_in`
- [ ] **T4.8** 錯誤帳密（帳號不存在）→ 401 "Invalid credentials"
- [ ] **T4.9** 錯誤帳密（密碼錯誤）→ 401 "Invalid credentials"（與 T4.8 相同訊息，防枚舉）
- [ ] **T4.10** 回應包含 `refresh_token` 寫入 httpOnly Cookie（`HttpOnly`、`Secure`、`SameSite=Lax`）
- [ ] **T4.11** Cookie `max_age` 為 30 天（60*60*24*30 秒）
- [ ] **T4.12** `web_sessions` 表寫入一筆新 record（`session_id`、`user_id`、`refresh_token_hash`）

### POST /api/v1/auth/refresh

- [ ] **T4.13** 無 `refresh_token` cookie → 401 "Missing refresh token"
- [ ] **T4.14** 有效 refresh_token → 200，回傳新 `access_token` + 新 cookie
- [ ] **T4.15** Refresh 成功後，舊 session 的 `refresh_token_hash` 已被 revoke（新舊不同）
- [ ] **T4.16** 使用已 revoke 的 refresh_token → 401 "Token reuse detected"
- [ ] **T4.17** 過期 refresh_token → 401 "Invalid or expired refresh token"

### POST /api/v1/auth/logout

- [ ] **T4.18** 有效 session → 200，`web_sessions` 中該 session 的 `revoked_at` 有時間戳
- [ ] **T4.19** 已被 revoke 的 session 再 logout → 仍然 200（冪等）

### GET /api/v1/auth/me

- [ ] **T4.20** 有效 token → 200，回傳 `{user_id, email, role}`
- [ ] **T4.21** 無 token 或無效 token → 401

---

## 領域 5：Google OAuth（Social Login）

### OAuth 流程 init

- [ ] **T5.1** `GET /api/v1/auth/login/google` → 200，回傳 `{redirect_url}` 包含 Google OAuth URL
- [ ] **T5.2** OAuth state token 寫入 Redis，TTL 10 分鐘，key 包含 `oauth:state:{state}`
- [ ] **T5.3** GitHub OAuth `GET /api/v1/auth/login/github` → 200，回傳 `{redirect_url}`

### OAuth Callback

- [ ] **T5.4** `GET /api/v1/auth/callback/google?code=...&state=...` state 不存在 → 400 "Invalid OAuth state"
- [ ] **T5.5** `GET /api/v1/auth/callback/google?code=...&state=...` state provider 不匹配 → 400
- [ ] **T5.6** 有效 callback：Google token exchange → userinfo API 呼叫成功
- [ ] **T5.7** 新用戶：自動建立 `users` 記錄（oauth_provider='google', oauth_subject=Google ID）
- [ ] **T5.8** 已存在用戶（同一 email）：復用既有 `users.id`，不重複建立
- [ ] **T5.9** `oauth_accounts` 表寫入 provider + subject unique 約束
- [ ] **T5.10** Callback 回傳 `{access_token, user_id}`
- [ ] **T5.11** 錯誤的 authorization code → Google API 回傳錯誤，callback 回 400

---

## 領域 6：WebSocket 即時通訊

### 連線建立

- [ ] **T6.1** `GET /ws/chat?token=<valid_access_token>` → WebSocket 101 Upgrade 成功
- [ ] **T6.2** 連線成功後第一個訊息：伺服器發送 `{"type": "connected", "session_id": "...", "server_time": "..."}`
- [ ] **T6.3** `GET /ws/chat?token=<invalid_token>` → 發送 `{"type": "auth_failed", "code": 4401}` 後關閉連線
- [ ] **T6.4** `GET /ws/chat?token=<expired_token>` → auth_failed + close (4401)
- [ ] **T6.5** 同一 session_id 同時兩次連線 → 第二次連線成功，第一次斷線
- [ ] **T6.6** `WebSocketConnectionManager.connection_count` 正確計數

### 訊息格式解析

- [ ] **T6.7** 發送 `{"type": "send_message", "mid": "xxx", "payload": {"content": "hello"}}` → 收到 `{"type": "message_ack", "payload": {"mid": "xxx"}, ...}`
- [ ] **T6.8** `send_message` 後緊接收到 `{"type": "typing", ...}` 打字提示
- [ ] **T6.9** 最終收到 `{"type": "message", "payload": {"content": "...", "source": "...", "confidence": ..., "knowledge_id": ...}}`
- [ ] **T6.10** 發送 `{"type": "ping"}` → 收到 `{"type": "pong"}`
- [ ] **T6.11** 發送 `{"type": "get_history", "payload": {"limit": 10}}` → 收到 `{"type": "history", "payload": {"messages": [...]}}`
- [ ] **T6.12** `get_history` limit 超過 100 → 取前 100 筆（上限截断）
- [ ] **T6.13** 發送 `{"type": "unknown_type"}` → 收到 `{"type": "error", "payload": {"detail": "Unknown type: unknown_type"}}`
- [ ] **T6.14** 發送非 JSON 格式文字 → 收到 `{"type": "error", "payload": {"detail": "Invalid JSON"}}`

### WebSocket 訊息路由

- [ ] **T6.15** `send_message` 空 content (`""`) → 無回應（早期返回）
- [ ] **T6.16** `send_message` content 為空白字元 → 無回應（.strip() 後為空）
- [ ] **T6.17** `typing_start` / `typing_end` → 收到 200 OK（或無回應），不 crash

### 訊息寫入資料庫

- [ ] **T6.18** `send_message` 後，`conversations` 表有一筆 platform='web' 的記錄
- [ ] **T6.19** `send_message` 後，`messages` 表有兩筆記錄（用戶訊息 + 機器人回覆）
- [ ] **T6.20** `web_conversations` 表有一筆對應記錄（browser, os, utm_* 欄位）

### Redis Pub/Sub（水平擴展）

- [ ] **T6.21** 連線時訂閱 `ws:session:{session_id}` Redis channel
- [ ] **T6.22** 斷線時取消訂閱 `ws:session:{session_id}`
- [ ] **T6.23** 透過 Redis `PUBLISH ws:session:{session_id} {...}` 可將訊息廣播至持有該 session 的實例
- [ ] **T6.24** 兩台伺服器實例：client A 連到實例 1，client B 連到實例 2，訊息可正確路由到雙方

### 斷線處理

- [ ] **T6.25** WebSocket disconnect (`code != 1000`) → `disconnect()` 清理 `connections` map
- [ ] **T6.26** 斷線後 Redis Pub/Sub subscription 已清除
- [ ] **T6.27** `WebSocketDisconnect` 例外被捕獲並記錄（logger.info）

### 打字提示（client → server）

- [ ] **T6.28** 發送 `{"type": "typing_start"}` → 機器人不回應（伺服器記錄意圖）
- [ ] **T6.29** 發送 `{"type": "typing_end"}` → 機器人不回應

### Feedback

- [ ] **T6.30** 發送 `{"type": "feedback", "payload": {"message_sid": "...", "rating": "positive"}}` → 寫入 `user_feedback` 表

---

## 領域 7：WebPlatformAdapter

### extract_user_context()

- [ ] **T7.1** 回傳 `platform=Platform.WEB`
- [ ] **T7.2** 回傳 `platform_user_id` 等於 `request.state.web_user.user_id`
- [ ] **T7.3** 回傳 `session_id` 等於 `request.state.web_user.session_id`
- [ ] **T7.4** `X-Forwarded-For: 1.2.3.4, 5.6.7.8` header → `_get_client_ip` 回傳 `1.2.3.4`
- [ ] **T7.5** 無 `X-Forwarded-For` → 回傳 `request.client.host`
- [ ] **T7.6** `request.client` 為 `None` → 回傳空字串

### supports_message_type()

- [ ] **T7.7** `MessageType.TEXT` → `True`
- [ ] **T7.8** `MessageType.IMAGE` → `False`
- [ ] **T7.9** `MessageType.AUDIO` → `False`

### get_capabilities()

- [ ] **T7.10** 回傳 `{typing_indicator: True, read_receipt: False, media_upload: False, multi_media: False}`

---

## 領域 8：資料庫 Schema（Migration）

### users 表擴展

- [ ] **T8.1** `ALTER TABLE`  migration 可成功執行（無錯誤）
- [ ] **T8.2** 新增 `password_hash` 欄位存在且可寫入 argon2id hash
- [ ] **T8.3** 新增 `email` 欄位 unique constraint 生效（重複 email → 錯誤）
- [ ] **T8.4** 新增 `email_verified` 預設值為 `FALSE`
- [ ] **T8.5** 新增 `oauth_provider` 可選（NULL 允許）
- [ ] **T8.6** 既有用戶記錄（telegram/line/whatsapp）不受到影響（password_hash 可為 NULL）

### web_sessions 表

- [ ] **T8.7** `session_id` 為 UUID unique constraint
- [ ] **T8.8** `user_id` FK 指向 `users(unified_user_id)`
- [ ] **T8.9** `refresh_token_hash` VARCHAR(64)
- [ ] **T8.10** `revoked_at` 可為 NULL（作用中 session）
- [ ] **T8.11** `idx_web_sessions_revoked` partial index 在 `WHERE revoked_at IS NULL` 時可用
- [ ] **T8.12** `expires_at` 欄位存在

### web_conversations 表

- [ ] **T8.13** `conversation_id` FK unique → 每個 conversation 最多一筆 web_conversations 記錄
- [ ] **T8.14** `browser`、`os`、`initial_referrer`、`utm_source/medium/campaign` 欄位存在

### oauth_accounts 表

- [ ] **T8.15** `(provider, provider_user_id)` unique constraint 生效（同一 Google ID 不能有兩筆記錄）
- [ ] **T8.16** `user_id` FK 指向 `users(unified_user_id)`
- [ ] **T8.17** `access_token_encrypted`、`refresh_token_encrypted` 欄位存在

### token_revocation_log 表

- [ ] **T8.18** `user_id`、`session_id`、`jti` 欄位存在
- [ ] **T8.19** `revoke_reason` 接受 `logout | token_reuse | expired | manual`
- [ ] **T8.20** `idx_token_revocation_user` index 在查詢時使用

### 隔離驗證

- [ ] **T8.21** Web 用戶（platform='web'）和既有用戶隔離查詢不受影響
- [ ] **T8.22** `conversations` 表查詢 `WHERE platform='web'` 不影響其他 platform 資料

---

## 領域 9：Rate Limiting（WebRateLimiter）

### 訊息頻率限制

- [ ] **T9.1** 30 秒內發送 30 條訊息 → 最後一條被拒绝（TokenBucket capacity=30）
- [ ] **T9.2** 30 條訊息後，等待 3 秒（refill_rate=10）→ 可再發送 10 條
- [ ] **T9.3** 未超限時 `check_message()` 回傳 `True`

### Session 建立限制

- [ ] **T9.4** 1 分鐘內建立 3 個 session → 第 4 個被拒绝
- [ ] **T9.5** 3 個 session 後，等待 20 秒 → 可再建立 1 個
- [ ] **T9.6** 未超限時 `check_session()` 回傳 `True`

### 鍵值隔離

- [ ] **T9.7** 用戶 A 的頻限不影響用戶 B（鍵值隔離：`web_msg:{user_id}`）

---

## 領域 10：CORS 配置

- [ ] **T10.1** `Access-Control-Allow-Origin` 為 `https://omnibot.example.com`（來自設定值）
- [ ] **T10.2** `Access-Control-Allow-Credentials: true`
- [ ] **T10.3** `Access-Control-Allow-Methods: GET, POST`
- [ ] **T10.4** `Access-Control-Allow-Headers: Authorization, Content-Type, X-Requested-With`
- [ ] **T10.5** `Access-Control-Expose-Headers: X-Request-ID`
- [ ] **T10.6** 未在 `allow_origins` 的網域 → CORS 拒絕（瀏覽器拋出錯誤）
- [ ] **T10.7** 預檢請求（OPTIONS）→ 200 + CORS headers（不經過 WebAuthMiddleware）

---

## 領域 11：Prometheus Metrics（Observability）

### WebSocket 專屬 Metrics

- [ ] **T11.1** `omnibot_websocket_connections_active` gauge = 目前活躍連線數（初始為 0）
- [ ] **T11.2** WebSocket 連線建立 → `omnibot_websocket_connections_active` +1
- [ ] **T11.3** WebSocket 斷線 → `omnibot_websocket_connections_active` -1
- [ ] **T11.4** 收到 `send_message` → `omnibot_websocket_messages_total{direction="inbound"}` +1
- [ ] **T11.5** 發出 `message` → `omnibot_websocket_messages_total{direction="outbound"}` +1
- [ ] **T11.6** 斷線原因 `client_close` → `omnibot_websocket_disconnect_total{reason="client_close"}` +1
- [ ] **T11.7** 斷線原因 `auth_failed` → `omnibot_websocket_disconnect_total{reason="auth_failed"}` +1
- [ ] **T11.8** 斷線原因 `timeout` → `omnibot_websocket_disconnect_total{reason="timeout"}` +1

### Auth Failure Metrics

- [ ] **T11.9** Invalid token → `omnibot_auth_failures_total{reason="invalid_token"}` +1
- [ ] **T11.10** Expired token → `omnibot_auth_failures_total{reason="expired_token"}` +1
- [ ] **T11.11** Session revoked → `omnibot_auth_failures_total{reason="session_revoked"}` +1
- [ ] **T11.12** Token reuse → `omnibot_auth_failures_total{reason="token_reuse"}` +1

### 既有 Metrics 擴展

- [ ] **T11.13** `omnibot_requests_total{platform="web"}` 可查詢（phase-web 不影響其他 platform）
- [ ] **T11.14** `omnibot_response_duration_seconds{platform="web"}` 可查詢

---

## 領域 12：部署架構（Infrastructure）

### Nginx WebSocket Proxy

- [ ] **T12.1** `location /ws/chat` proxy_pass 指向 `upstream omnibot_websocket`（port 8001）
- [ ] **T12.2** 具備 `proxy_http_version 1.1`
- [ ] **T12.3** 具備 `proxy_set_header Upgrade $http_upgrade`
- [ ] **T12.4** 具備 `proxy_set_header Connection "upgrade"`
- [ ] **T12.5** `proxy_read_timeout` 為 86400 秒
- [ ] **T12.6** `proxy_send_timeout` 為 86400 秒
- [ ] **T12.7** SSL certificate 和 key 設定正確

### Docker Compose

- [ ] **T12.8** `omnibot-api` 環境變數包含 `JWT_SECRET_KEY`
- [ ] **T12.9** `omnibot-api` 環境變數包含 `WEB_CORS_ORIGINS`
- [ ] **T12.10** `omnibot-api` ports 映射 `8000:8000` 和 `8001:8001`
- [ ] **T12.11** Redis 啟用 `notify-keyspace-events Ex`（key 過期通知）
- [ ] **T12.12** Nginx 設定掛載 `nginx/web.conf` 為唯讀

### Kubernetes

- [ ] **T12.13** `ConfigMap` 包含 `JWT_SECRET_KEY` 和 `WEB_CORS_ORIGINS`
- [ ] **T12.14** `Deployment` container ports 包含 `8000` 和 `8001`
- [ ] **T12.15** `Ingress` annotation `proxy-read-timeout: "86400"`
- [ ] **T12.16** `Ingress` `/ws/chat` path 導向 port `8001`（WebSocket 專用）
- [ ] **T12.17** `Ingress` `/api/` path 導向 port `8000`
- [ ] **T12.18** `Ingress` `/` path 導向 `web-frontend` service port `80`

---

## 領域 13：前端 Chat UI（MVP）

### 登入 / 註冊

- [ ] **T13.1** 登入表單提交 email + password → 收到 access_token 和 refresh_token (in cookie)
- [ ] **T13.2** 登入失敗（錯誤帳密）→ 顯示 "Invalid credentials"，不透露具體原因
- [ ] **T13.3** 註冊成功 → 自動登入或導向登入頁
- [ ] **T13.4** Social Login 按鈕點擊 → 導向 OAuth 授權 URL
- [ ] **T13.5** OAuth callback URL 包含 access_token → 前端儲存並開始 WebSocket 連線

### WebSocket 連線

- [ ] **T13.6** 頁面載入後，使用 `?token=<access_token>` 連線 WebSocket
- [ ] **T13.7** 收到 `{"type": "connected"}` → 顯示連線狀態為「已連線」
- [ ] **T13.8** 收到 `{"type": "auth_failed"}` → 顯示「連線失敗，請重新登入」提示
- [ ] **T13.9** 多分頁：每個分頁有獨立 WebSocket 連線（不同 session_id）

### 訊息收發

- [ ] **T13.10** 輸入文字並發送 → 顯示「送出的訊息」+ 灰底 + 送達勾（收到 MESSAGE_ACK）
- [ ] **T13.11** 收到 `{"type": "typing"}` → 顯示「對方正在輸入...」
- [ ] **T13.12** 收到 `{"type": "message"}` → 顯示「機器人回覆」訊息
- [ ] **T13.13** 訊息列表可滾動，自動滾到最新訊息
- [ ] **T13.14** `get_history` 在連線建立後主動呼叫，載入歷史訊息

### 斷線重連

- [ ] **T13.15** 斷線後 1 秒自動重連（指數退避：1s, 2s, 4s, 8s, 16s，最多 5 次）
- [ ] **T13.16** 第 5 次重連失敗 → 顯示「連線中斷，請檢查網路」提示，停止重試
- [ ] **T13.17** 收到 `auth_failed`（4401）→ 先 `POST /auth/refresh`，取得新 token 後重試連線
- [ ] **T13.18** Refresh 失敗（token 已無效）→ 顯示「Session 過期，請重新登入」
- [ ] **T13.19** 重新連線成功後 → 自動呼叫 `get_history` 補回漏收訊息

### Session 過期

- [ ] **T13.20** Access token 過期時（前端的 4401）→ 自動呼叫 `/auth/refresh`
- [ ] **T13.21** Refresh token 30 天期滿 → 顯示「請重新登入」提示

### 響應式與無障礙

- [ ] **T13.22** Mobile Safari（375px）下 Chat UI 可正常操作
- [ ] **T13.23** Chrome Android（412px）下 Chat UI 可正常操作
- [ ] **T13.24** 所有輸入框有 `aria-label`
- [ ] **T13.25** 訊息列表支援鍵盤上下滾動（Tab / Shift+Tab）
- [ ] **T13.26** 連線狀態指示器（綠點=已連線，紅點=斷線）

---

## 領域 14：驗收標準（KPI 對應測試）

### 商業 KPI

- [ ] **T14.1** **Web FCR >= 75%**：SQL `SELECT COUNT(*) FROM messages m JOIN conversations c ON m.conversation_id = c.id WHERE c.platform = 'web' AND m.is_bot = TRUE AND m.fcr = TRUE` / 總 bot 訊息數 >= 0.75
- [ ] **T14.2** **p95 WebSocket 延遲 < 1.5s**：定時 `ping`/`pong` 測量，p95(RTT) < 1500ms
- [ ] **T14.3** **登入轉化率 > 90%**：`success_login_count / login_attempt_count` >= 0.90
- [ ] **T14.4** **Refresh Token Rotation 100%**：自動化測試：refresh 前舊 jti 無法使用
- [ ] **T14.5** **Session 安全 0 token reuse**：滲透測試腳本重放已用 refresh token，驗證回 401
- [ ] **T14.6** **WebSocket 斷線復原 < 5s**：模擬斷線，測量從斷線到重連成功的時間 < 5000ms
- [ ] **T14.7** **CORS 無漏洞**：自動化工具（e.g. corsy）確認無 `Access-Control-Allow-Origin: *` + `Access-Control-Allow-Credentials: true`
- [ ] **T14.8** **同時 WebSocket 連線 >= 1000/實例**：負載測試工具（e.g. Artillery）建立 1000 連線，全部成功收發訊息

### 安全性滲透測試

- [ ] **T14.9** 暴力破解：5 次錯誤登入後 → 第 6 次被 rate limit（429）
- [ ] **T14.10** JWT 猜測：使用假 JWT 不被接受（無條件進入）
- [ ] **T14.11** CSRF：無 state token 的 OAuth callback 被拒絕
- [ ] **T14.12** XSS：`<script>alert(1)</script>` 發送到 Chat UI，確認未執行（輸出轉義）

### 壓力測試

- [ ] **T14.13** 1000 個並發 WebSocket 連線，訊息延遲不超過 2 秒（考慮額外負載）
- [ ] **T14.14** Redis Pub/Sub 跨 3 個實例廣播，訊息送達所有實例 < 100ms
- [ ] **T14.15** 資料庫：`web_sessions` 表 100k 筆記錄，`revoked_at IS NULL` 查詢效能 < 10ms

---

## 整合測試（End-to-End）

### 完整登入 → 聊天流程

- [ ] **T15.1** `POST /auth/register` → `POST /auth/login` → WebSocket 連線 → `send_message` → 收到 `message` 回覆 → `POST /auth/logout` → 全部成功

### OAuth → 聊天流程

- [ ] **T15.2** `GET /auth/login/google` → OAuth 授權 → `GET /auth/callback/google` → WebSocket 連線 → 聊天

### 多實例水平擴展

- [ ] **T15.3** 實例 1 和實例 2 同時運行，client A 連實例 1、client B 連實例 2，client A 發訊息，client B 能在 Redis Pub/Sub 協助下收到回覆（跨實例廣播）

### 災難復原

- [ ] **T15.4** 主要實例掛掉 → client 自動重連到備援實例，session 恢復，聊天不中斷

---

## 測試覆蓋率目標

| 等級 | 覆蓋率目標 |
|------|-----------|
| Unit（領域 1-7） | >= 90% branch coverage |
| Integration（領域 8-12） | 每個 migration / 部署要素 >= 1 個通過的測試 |
| E2E（領域 13-15） | 核心流程（登入→聊天→登出）100% 通過 |
| Security（滲透） | 所有威脅向量的對應緩解措施有對應測試 |

---

## 執行順序建議（TDD 驅動）

```
Phase 1：領域 1（JWT）+ 領域 2（密碼）
Phase 2：領域 3（Middleware）+ 領域 4（Auth Endpoints）
Phase 3：領域 5（OAuth）
Phase 4：領域 8（DB Schema Migration）先行
Phase 5：領域 6（WebSocket）
Phase 6：領域 7（WebPlatformAdapter）
Phase 7：領域 9（Rate Limiting）
Phase 8：領域 10（CORS）
Phase 9：領域 11（Metrics）
Phase 10：領域 12（Deployment — 容器化測試）
Phase 11：領域 13（前端 E2E）
Phase 12：領域 14（KPI 驗收 + 滲透測試）
Phase 13：領域 15（整合 E2E）
```

---

*文件版本：v1.0*  
*依據：SPEC/omnibot-phase-web.md*  
*最後更新：2026-05-01*
