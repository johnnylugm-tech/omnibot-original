# OmniBot Phase Voice — TDD 驗證清單

---

## 規格文件對應

| 來源檔案 | 資料夾 |
|---------|--------|
| `SPEC/omnibot-phase-voice.md` | `SPEC/` |
| 本檔案 | `SPEC/omnibot-phase-voice-tdd-checklist.md` |

---

## 覆蓋範圍

本清單以 `SPEC/omnibot-phase-voice.md` 為**唯一主要來源**，對所有功能區塊進行 100% 拆解對應。Phase 1-3 既有模組（Layer 1-4、InputSanitizer、PII Masking、Emotion Analyzer、DST、Grounding Checks、Escalation Manager）不在本 Phase Voice 實作範圍內，不列入測試。

---

## 測試優先順序

| 等級 | 說明 |
|------|------|
| P0 | 核心路徑失敗會導致服務無法上線（Twilio Webhook、IVR Engine、ASR/TTS） |
| P1 | 重要功能但不阻断发布（Rate Limiter、Authenticator、Emotion Analyzer） |
| P2 | 輔助功能（Dashboard、Schema細節、既有系統斷言） |

---

## 測試領域分組

---

### 領域 1：Twilio Webhook 接收與驗證

**組件**：`TwilioAdapter`、`/api/v1/voice/webhook/twilio/incoming`、`/api/v1/voice/webhook/twilio/status`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 1.1 | `TwilioAdapter.verify_webhook()` — 正確 HMAC-SHA1 簽名 | 驗證通過，回傳 `True` | P0 |
| 1.2 | `TwilioAdapter.verify_webhook()` — 錯誤簽名 | 驗證失敗，回傳 `False`，不回傳內部錯誤 | P0 |
| 1.3 | `TwilioAdapter.verify_webhook()` — 空白 body | 不拋例外的優雅處理 | P0 |
| 1.4 | `TwilioAdapter.parse_incoming_call()` — 正常 Twilio form | 正確解析 `CallSid`、`From`、`To`、`CallStatus` | P0 |
| 1.5 | `TwilioAdapter.parse_incoming_call()` — 缺少必要欄位 | 拋出 `KeyError`（或回傳錯誤），不崩潰 | P0 |
| 1.6 | `TwilioAdapter._anonymize()` — 國際號碼（+886912345678）| 輸出格式 `+886****5678` | P0 |
| 1.7 | `TwilioAdapter._anonymize()` — 短號（+123）| 長度 <= 4 時直接回傳 | P0 |
| 1.8 | `TwilioAdapter._anonymize()` — 純數字（0912345678）| 保留最後 4 碼，前方脫敏 | P0 |
| 1.9 | POST `/api/v1/voice/webhook/twilio/incoming` — 無效 Twilio 簽名 | HTTP 401，`{"error": "invalid_signature"}` | P0 |
| 1.10 | POST `/api/v1/voice/webhook/twilio/incoming` — 有效簽名，正常來話 | HTTP 200，TwiML XML 回應 | P0 |
| 1.11 | POST `/api/v1/voice/webhook/twilio/status` — Twilio status callback | HTTP 200，更新 `voice_calls` 記錄狀態 | P0 |
| 1.12 | `CallDirection` enum — `INBOUND` / `OUTBOUND` 成員 | 枚舉值正確 | P1 |
| 1.13 | `CallStatus` enum — 7 種狀態成員 | 枚舉值正確 | P1 |
| 1.14 | Webhook URL — HTTP 非 200 回應時 Twilio 重試邏輯 | 符合 Twilio 重試條件（3xx/4xx/5xx） | P1 |
| 1.15 | Webhook URL — 接收空白 POST body | HTTP 400，不崩潰 | P1 |

---

### 領域 2：電話號碼脫敏

**組件**：`TwilioAdapter._anonymize()`、`voice_caller_mappings` 表

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 2.1 | 脫敏函式 — 標準國際格式（+886912345678）| 保留國碼前 4 碼，最後 4 碼，其餘 `*` | P0 |
| 2.2 | 脫敏函式 — 美國格式（+12025551234）| 正確置換 | P0 |
| 2.3 | 脫敏函式 — 短號（+86）| 長度不足 4 碼時不回傳錯誤 | P0 |
| 2.4 | `voice_caller_mappings` 表 — 原始號碼唯一約束 | 同一 `raw_caller_number` 不可重複 INSERT | P1 |
| 2.5 | `voice_caller_mappings` 表 — `raw_caller_number` 不在一般 API 回應中暴露 | 僅回傳 `anonymized_number` | P1 |
| 2.6 | `raw_caller_number` 欄位 — 嚴格存取控制（僅 VoiceAuthenticator 內部使用）| 其他模組無法直接查詢 | P1 |
| 2.7 | `voice_caller_mappings` 表 — `last_verified_at` 更新時機 | 每次成功 ANI 驗證後更新 | P2 |
| 2.8 | `voice_caller_mappings` 表 — `unified_user_id` 為 NULL 時（未匹配）| 查詢回傳 None，不崩潰 | P1 |

---

### 領域 3：VoicePlatformAdapter

**組件**：`VoicePlatformAdapter`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 3.1 | `extract_user_context(CallEvent)` — 回傳 `platform=Platform.VOICE` | 平臺識別正確 | P0 |
| 3.2 | `extract_user_context(CallEvent)` — `platform_user_id` 為脫敏後電話號碼 | 脫敏號碼用於 `platform_user_id` | P0 |
| 3.3 | `extract_user_context(CallEvent)` — `call_id` 正確對應 `CallEvent.call_sid` | 通話追蹤 ID 正確 | P0 |
| 3.4 | `extract_user_context(CallEvent)` — `direction` 正確映射 | INBOUND/OUTBOUND 正確 | P1 |
| 3.5 | `supports_message_type(MessageType.TEXT)` — 回傳 `True` | ASR 轉文字後的文字輸入被接受 | P0 |
| 3.6 | `supports_message_type(MessageType.DTMF)` — 回傳 `True` | DTMF 按鍵輸入被接受 | P0 |
| 3.7 | `supports_message_type(MessageType.IMAGE)` — 回傳 `False` | 語音入口不支援圖片 | P0 |
| 3.8 | `get_capabilities()` — 回傳 `{"voice": True, "dtmf": True, "tts": True, "asr": True}` | 能力報告正確 | P0 |
| 3.9 | `get_capabilities()` — `recording=False`（Phase Voice-2 才支援）| 目前階段記錄為 False | P1 |
| 3.10 | `response_to_voice(UnifiedResponse)` — 回傳 `response.content` 文字 | TTS 輸入為回覆文字 | P0 |

---

### 領域 4：IVR 流程定義（資料結構）

**組件**：`IVRNode`、`IVRFlow`、`IVRSession`、`IVRNodeType`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 4.1 | `IVRNodeType` enum — 6 種節點類型成員 | PROMPT/MENU/COLLECT/TRANSFER/CONDITION/END | P0 |
| 4.2 | `IVRNode` — `node_id` 必填 | 建立時不可省略 | P0 |
| 4.3 | `IVRNode` — `type` 必填 | 建立時不可省略 | P0 |
| 4.4 | `IVRNode` — `next_nodes` 預設空 dict | 未指定時不拋錯 | P0 |
| 4.5 | `IVRNode` — `timeout_seconds` 預設 5 | 未指定時為 5 秒 | P1 |
| 4.6 | `IVRNode` — `max_retries` 預設 2 | 未指定時為 2 次 | P1 |
| 4.7 | `IVRNode` — COLLECT 節點 `asr_model` 可選 | 可以為 None | P1 |
| 4.8 | `IVRNode` — COLLECT 節點 `expected_intents` 可選 | 可以為 None | P1 |
| 4.9 | `IVRFlow` — `flow_id` + `version` 唯一約束 | 同一 `flow_id` 的不同 version 為不同流程 | P1 |
| 4.10 | `IVRFlow` — `entry_node_id` 必須存在於 `nodes` 中 | 啟動時斷言驗證 | P0 |
| 4.11 | `IVRFlow` — `nodes` dict 的每個 `node_id` 對應有效的 `IVRNode` | 資料一致性 | P1 |
| 4.12 | `IVRSession` — `call_id` 必填 | 建立時不可省略 | P0 |
| 4.13 | `IVRSession` — `retry_count` 預設 0 | 未超時重試時為 0 | P1 |
| 4.14 | `IVRSession` — `collected_input` 預設空字串 | 初始無收集輸入 | P1 |
| 4.15 | `IVRSession` — `conversation_id` 可為 None | IVR 剛啟動時可為 None | P1 |

---

### 領域 5：IVR Engine — 節點執行

**組件**：`IVREngine._execute_node()`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 5.1 | `PROMPT` 節點執行 — 回傳 TwiML `<Say>` XML | `TwiMLResponse.to_xml()` + `say()` 正確 | P0 |
| 5.2 | `PROMPT` 節點執行 — `language="zh-TW"` 參數傳遞 | TTS 語言設定正確 | P1 |
| 5.3 | `MENU` 節點執行 — 回傳 TwiML `<Gather>` XML | `gather()` 包含正確 `numDigits`/`timeout`/`prompt` | P0 |
| 5.4 | `MENU` 節點執行 — `numDigits` 預設 1 | 未指定時只收集 1 位 | P1 |
| 5.5 | `MENU` 節點執行 — `timeout` 為 `timeout_seconds` | 等待超時時間正確 | P1 |
| 5.6 | `COLLECT` 節點執行 — 回傳 TwiML 含 `<Say>` + 語音收集 | 執行邏輯正確 | P0 |
| 5.7 | `TRANSFER` 節點執行 — 回傳 TwiML 含 `<Say>` + `<Dial>` | 轉接人工客服 XML 正確 | P0 |
| 5.8 | `TRANSFER` 節點執行 — `next_nodes["__agent__"]` 取得正確分機號 | 轉接目標正確 | P0 |
| 5.9 | `TRANSFER` 節點執行 — 朗讀「正在為您轉接客服人員，請稍候」 | TTS 文字正確 | P1 |
| 5.10 | `END` 節點執行 — 回傳 `<Say>` + `<Hangup/>` | 正確結束 XML | P0 |
| 5.11 | `END` 節點執行 — 朗讀「感謝來電，再見」 | TTS 文字正確 | P1 |
| 5.12 | 未知節點類型 — 回傳 `<Hangup/>` 而非崩潰 | 未知類型 graceful fallback | P0 |
| 5.13 | `IVREngine.start()` — 初始化 `IVRSession` 並執行 entry node | 流程正確啟動 | P0 |
| 5.14 | `IVREngine.start()` — 回傳第一個 TwiML XML 字串 | TwiML 可直接回傳給 Twilio | P0 |

---

### 領域 6：IVR Engine — 路由邏輯

**組件**：`IVREngine.handle_input()`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 6.1 | `MENU` 節點 — 有效 DTMF 按鍵（"1"）| 正確路由到 `next_nodes["1"]` | P0 |
| 6.2 | `MENU` 節點 — 無效 DTMF 按鍵（"9"，未定義）| 路由到 `__timeout__` fallback | P0 |
| 6.3 | `MENU` 節點 — 連續超時（無按鍵）| `retry_count` 遞增 | P0 |
| 6.4 | `MENU` 節點 — `max_retries=2` 時第三次超時 | 路由到 INVALID_INPUT 或 END | P0 |
| 6.5 | `COLLECT` 節點 — 收到 ASR transcript → Intent Router | 文字輸入送往 Intent Router | P0 |
| 6.6 | `COLLECT` 節點 — Intent Router 回傳預期意圖 | 正確路由到對應 `next_nodes` 條目 | P0 |
| 6.7 | `COLLECT` 節點 — Intent Router 回傳非預期意圖 | fallback 到 `__fallback__` 條目 | P0 |
| 6.8 | `COLLECT` 節點 — Intent Router 回傳空意圖 | 合理處理，不崩潰 | P1 |
| 6.9 | `handle_input()` — 更新 `current_node_id` 為下一節點 | Session 狀態正確更新 | P0 |
| 6.10 | `handle_input()` — 重試計數在有效輸入後重置為 0 | 有效按鍵後 `retry_count` 歸零 | P1 |
| 6.11 | `handle_input()` — `next_node_id` 為 None 時（無效路由）| 回傳 `<Hangup/>` | P0 |
| 6.12 | IVR Flow 範例 — WELCOME → MAIN_MENU → 按 "1" → ORDER_INQUIRY | 完整流程驗證 | P1 |
| 6.13 | IVR Flow 範例 — MAIN_MENU 超時 2 次 → END | 重試耗盡後正確結束 | P1 |
| 6.14 | IVR Flow 範例 — MAIN_MENU 按 "3" → TRANSFER_AGENT | 轉接流程正確觸發 | P1 |

---

### 領域 7：IVR Flow 管理 API

**組件**：IVR Flow CRUD、`ivr_flows` 表

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 7.1 | 建立新 IVR Flow — `flow_id` + `version=1` 寫入資料庫 | `ivr_flows` 表正確 INSERT | P0 |
| 7.2 | 新增 IVR Flow 版本 — `flow_id` 相同但 `version=2` | 版本遞增正確 | P0 |
| 7.3 | 同一 `flow_id` + 同一 `version` 不可重複 | `UNIQUE(flow_id, version)` 約束生效 | P0 |
| 7.4 | 啟用新版本 — `is_active=TRUE`，舊版本應改為 `is_active=FALSE` | 最多只有一個啟用版本 | P0 |
| 5 | 查詢啟用中的 Flow — `WHERE is_active=TRUE` 回傳正確 flow_id | 來話時載入正確流程 | P0 |
| 7.6 | `nodes` JSONB 序列化 — IVRFlow 物件完整序列化後可還原 | JSON round-trip | P1 |
| 7.7 | `ivr_flows` 表 — `created_by` 正確記錄建立者 UUID | 操作審計追蹤 | P2 |
| 7.8 | 嘗試刪除啟用中的 Flow — 應被拒絕或先停用 | 不允許刪除 active flow | P1 |
| 7.9 | 列出所有版本 — `SELECT * FROM ivr_flows WHERE flow_id=%s ORDER BY version` | 版本歷史完整 | P2 |
| 7.10 | IVR Flow 不存在時查詢 — 回傳 404 或 None | 不崩潰 | P1 |

---

### 領域 8：ASR Adapter

**組件**：`ASRAdapter` ABC、`WhisperASRAdapter`、`GoogleSTTAdapter`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 8.1 | `WhisperASRAdapter` — 正確初始化（`api_url` + `model`）| 實例建立成功 | P0 |
| 8.2 | `WhisperASRAdapter.transcribe()` — 有效音訊 URL | 回傳非空文字 transcript | P0 |
| 8.3 | `WhisperASRAdapter.transcribe()` — 預設 `language="zh-TW"` | 語言參數傳遞正確 | P1 |
| 8.4 | `WhisperASRAdapter.transcribe()` — ASR API 回應 500 錯誤 | 拋出 `ASRError`，不回傳空字串 | P0 |
| 8.5 | `WhisperASRAdapter.transcribe()` — API URL 無法連線 | 拋出 `ConnectionError` | P0 |
| 8.6 | `WhisperASRAdapter.transcribe()` — 逾時 30 秒 | `asyncio.timeout(30)` 正確運作 | P0 |
| 8.7 | `WhisperASRAdapter.transcribe()` — 空音訊 URL | 回傳空字串或拋出明確錯誤 | P1 |
| 8.8 | `WhisperASRAdapter.transcribe()` — `model="large-v3"` 參數傳遞 | 模型名稱正確傳遞 | P1 |
| 8.9 | `GoogleSTTAdapter` — 正確初始化 | 實例建立成功 | P1 |
| 8.10 | `GoogleSTTAdapter.transcribe()` — API 實作存在 | 方法可調用 | P1 |
| 8.11 | `ASRAdapter` ABC — `transcribe` 為抽象方法 | 子類必須實作 | P0 |
| 8.12 | 兩種 ASR 實作置換 — `ASRAdapter` ABC 參數可接受任一實作 | 符合依赖反转（DIP） | P1 |
| 8.13 | ASR 錯誤時 `IVREngine.handle_input()` — 應該 gracefully 結束或重試 | 不卡住通話 | P0 |

---

### 領域 9：TTS Adapter

**組件**：`TTSAdapter` ABC、`GoogleTTSAdapter`、`SSMLBuilder`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 9.1 | `GoogleTTSAdapter` — 正確初始化（`api_key`）| 實例建立成功 | P0 |
| 9.2 | `GoogleTTSAdapter.synthesize()` — 有效文字 | 回傳 `data:audio/mp3;base64,...` 格式 | P0 |
| 9.3 | `GoogleTTSAdapter.synthesize()` — 預設 `voice="zh-TW-Standard-A"` | 語音參數正確 | P1 |
| 9.4 | `GoogleTTSAdapter.synthesize()` — 預設 `speaking_rate=1.0` | 語速參數正確 | P1 |
| 9.5 | `GoogleTTSAdapter.synthesize()` — API 回應 400（無效文字）| 拋出明確錯誤 | P0 |
| 9.6 | `GoogleTTSAdapter.synthesize()` — API 回應 401（無效 API Key）| 拋出認證錯誤 | P0 |
| 9.7 | `SSMLBuilder.build()` — 回傳 `<speak><prosody ...>text</prosody></speak>` | SSML 標記格式正確 | P1 |
| 9.8 | `SSMLBuilder.build(rate=0.8)` — `prosody rate="0.8"` | 語速參數正確嵌入 | P1 |
| 9.9 | `SSMLBuilder.build(pitch="+2st")` — `prosody pitch="+2st"` | 音調參數正確嵌入 | P1 |
| 9.10 | `SSMLBuilder.add_pause(500)` — 回傳 `<break time="500ms"/>` | 停頓標記正確 | P1 |
| 9.11 | `SSMLBuilder.add_pause()` — 預設 `duration_ms=500` | 預設值正確 | P1 |
| 9.12 | `TTSAdapter` ABC — `synthesize` 為抽象方法 | 子類必須實作 | P0 |
| 9.13 | TTS 錯誤時 `IVREngine._execute_node()` — graceful fallback，不卡住通話 | 錯誤處理正確 | P0 |

---

### 領域 10：Voice Emotion Analyzer

**組件**：`VoiceEmotionAnalyzer`、`VoiceEmotionCategory`、`VoiceEmotionScore`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 10.1 | `VoiceEmotionCategory` enum — 6 種情緒成員 | NEUTRAL/ANGRY/FRUSTRATED/CONFUSED/SILENT/HURRIED | P0 |
| 10.2 | `VoiceEmotionScore` dataclass — 所有欄位型別正確 | category/intensity/pitch_avg/speech_rate/energy/silence_ratio | P0 |
| 10.3 | `_classify()` — `silence_ratio > 0.5` → `SILENT` | 靜默偵測正確 | P0 |
| 10.4 | `_classify()` — `energy > 0.8` AND `speech_rate > 1.3` → `ANGRY` | 生氣偵測正確 | P0 |
| 10.5 | `_classify()` — `speech_rate < 0.6` → `CONFUSED` | 困惑偵測正確 | P0 |
| 10.6 | `_classify()` — 不符合所有條件 → `NEUTRAL` | 預設情緒正確 | P0 |
| 10.7 | `analyze()` — 正常音訊 URL | 回傳 `VoiceEmotionScore` 且 `category` 不為 None | P0 |
| 10.8 | `analyze()` — 每通電話維護獨立的 `_call_emotions[call_id]` | 不同通話情緒歷史隔離 | P0 |
| 10.9 | `analyze()` — 多次呼叫同一 `call_id` → history 累加 | 情緒歷史正確 append | P1 |
| 10.10 | `should_escalate()` — 連續 3 次 ANGRY → `(True, "voice_emotion_negative")` | 情緒轉接觸發正確 | P0 |
| 10.11 | `should_escalate()` — 連續 2 次 `silence_ratio > 0.5` → `(True, "voice_silence_too_long")` | 靜默轉接觸發正確 | P0 |
| 10.12 | `should_escalate()` — 只有 1 次記錄時 | 回傳 `(False, "")`（樣本不足）| P0 |
| 10.13 | `should_escalate()` — 連續 2 次 ANGRY（不足 3 次）| 回傳 `(False, "")` | P1 |
| 10.14 | `_extract_features()` — 正常音訊 URL 回傳 4 個浮點數 | pitch/speech_rate/energy/silence_ratio | P0 |
| 10.15 | `VoiceEmotionAnalyzer` — `min_confidence=0.7` 影響分類閾值 | 信心閾值正確運作 | P1 |
| 10.16 | `voice_emotion_history` 表寫入 — `analyze()` 結果寫入資料庫 | SQL INSERT 正確 | P2 |
| 10.17 | 情緒為 `SILENT` 時的 IVR 行為 — 詢問「請問需要幫忙嗎」| 具體回應邏輯（可選，Phase Voice-2） | P2 |

---

### 領域 11：Voice Authenticator

**組件**：`VoiceAuthenticator`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 11.1 | `authenticate_by_ani()` — ANI 匹配既有用戶 | 回傳 `unified_user_id` + 使用者資料 | P0 |
| 11.2 | `authenticate_by_ani()` — ANI 無匹配記錄 | 回傳 `None`，不拋例外 | P0 |
| 11.3 | `authenticate_by_pin()` — 正確 PIN | 回傳 `True` | P0 |
| 11.4 | `authenticate_by_pin()` — 錯誤 PIN | 回傳 `False`，不暴露內部資訊 | P0 |
| 11.5 | `authenticate_by_pin()` — 使用者無 `voice_pin_hash` | 回傳 `False`，不崩潰 | P0 |
| 11.6 | `authenticate_by_pin()` — 正確 PIN，`voice_pin_hash` 以 argon2 格式驗證 | argon2 verify 正確 | P1 |
| 11.7 | `get_or_create_voice_user()` — ANI 匹配既有用戶 | 回傳既有用戶，`authenticated=True` | P0 |
| 11.8 | `get_or_create_voice_user()` — ANI 無匹配，新建匿名用戶 | INSERT 新紀錄，回傳新 UUID | P0 |
| 11.9 | `get_or_create_voice_user()` — `authenticated=False` 時新建匿名用戶 | 匿名用戶標記正確 | P0 |
| 11.10 | 連續 3 次錯誤 PIN — 帳戶鎖定邏輯 | 第 3 次失敗後 PIN 驗證被拒絕 | P1 |
| 11.11 | PIN 鎖定後 — 正確 PIN 仍無法通過 | 鎖定狀態正確強制執行 | P1 |
| 11.12 | `voice_caller_mappings` 表 — `raw_caller_number` → `unified_user_id` 映射 | Mapping Table 正確維護 | P1 |
| 11.13 | `users.voice_pin_hash` 欄位可 NULL — 無 PIN 的用戶（ANI 識別足夠）| 欄位允許 NULL | P1 |

---

### 領域 12：Voice Call Orchestrator

**組件**：`VoiceCallOrchestrator`、`CallState`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 12.1 | `CallState` enum — 7+ 種狀態成員 | INCOMING/RINGING/IVR/BRIDGED/TRANSFERRING/COMPLETED/NO_ANSWER/FAILED | P0 |
| 12.2 | `handle_incoming_call()` — 來話時寫入 `voice_calls` 表 | INSERT 正確，`status=INCOMING` | P0 |
| 12.3 | `handle_incoming_call()` — `caller_number` 脫敏寫入 | 脫敏號碼用於資料庫 | P0 |
| 12.4 | `handle_incoming_call()` — 建立 `IVRSession` 並啟動 IVR | `IVREngine.start()` 正確觸發 | P0 |
| 12.5 | 來話接通 → `answered_at` 更新 | `CallStatus.ANSWERED` callback 正確更新時間戳 | P0 |
| 12.6 | 通話結束 → `ended_at` + `duration_seconds` 寫入 | `CallStatus.COMPLETED` callback 正確計算時長 | P0 |
| 12.7 | 來話未接 → `end_reason="no_answer"` | `CallStatus.NO_ANSWER` 正確映射 | P0 |
| 12.8 | 通話失敗 → `end_reason="failed"` | `CallStatus.FAILED` 正確映射 | P0 |
| 12.9 | 轉接人工 → `end_reason="transferred"` | TRANSFER 節點觸發後正確標記 | P0 |
| 12.10 | 通話提前放棄（abandoned）→ `end_reason="abandoned"` | 振鈴後使用者掛斷的正確標記 | P1 |
| 12.11 | `asr_provider` 欄位寫入 | 記錄使用哪個 ASR 引擎 | P2 |
| 12.12 | `tts_provider` 欄位寫入 | 記錄使用哪個 TTS 引擎 | P2 |
| 12.13 | `orchestrator` — `CallState` 轉換合法性 | 不允許 INCOMING → COMPLETED（跳過 ANSWERED）| P1 |

---

### 領域 13：Voice Rate Limiter

**組件**：`VoiceRateLimiter`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 13.1 | `check_incoming_call()` — 新來話，無限制 | 回傳 `(True, "")` | P0 |
| 13.2 | `check_incoming_call()` — 冷卻期中 | 回傳 `(False, "cooldown")` | P0 |
| 13.3 | `check_incoming_call()` — 今日通話 >= 10 通 | 回傳 `(False, "daily_limit")` | P0 |
| 13.4 | `on_call_started()` — 來話接通，Redis `calls:today:{number}` +1 | `INCR` 正確 | P0 |
| 13.5 | `on_call_started()` — TTL = 86400 秒（24 小時）| `EXPIRE` 正確設定 | P0 |
| 13.6 | `on_call_ended()` — 設定冷卻期 1 分鐘 | `SETEX` 60 秒正確 | P0 |
| 13.7 | 每日次數限制 — 第 10 通來話允許，第 11 通拒絕 | 邊界條件正確 | P0 |
| 13.8 | 每日次數限制 — 隔天（UTC）自動重置 | UTC 日期跨越後次數歸零 | P1 |
| 13.9 | `MAX_CALL_DURATION_MINUTES = 10` — 時長超時掛斷邏輯 | 逾時中斷通話 | P1 |
| 13.10 | Rate Limit 回傳 `VOICE_RATE_LIMITED (429)` — HTTP status 正確 | API 層正確處理 | P0 |
| 13.11 | Redis 連線失敗時 — `check_incoming_call()` 的 fallback 行為 | 應該允許通過（fail-open）或回傳可識別錯誤 | P1 |
| 13.12 | 多實例部署時 Redis 原子性 — `INCR` 操作原子性 | Redis 單命令原子操作 | P1 |

---

### 領域 14：TwiML 回應建構

**組件**：`TwiMLResponse`

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 14.1 | `say()` — 回傳 `<Say voice="..." language="...">text</Say>` | XML 格式正確 | P0 |
| 14.2 | `say()` — 預設 `voice="alice"`, `language="zh-TW"` | 預設參數正確 | P1 |
| 14.3 | `say()` — 特殊字元轉義（`&` → `&amp;`, `<` → `&lt;`）| SSRF/注入防護 | P0 |
| 14.4 | `gather()` — 回傳 `<Gather numDigits="..." timeout="...">...</Gather>` | XML 格式正確 | P0 |
| 14.5 | `gather()` — 預設 `numDigits=1`, `timeout=5` | 預設值正確 | P1 |
| 14.6 | `gather()` — 內含 `<Say>` 子元素 | 巢狀 XML 正確 | P0 |
| 14.7 | `record()` — 回傳 `<Record maxDuration="..." transcribe="..."/>` | 自閉合標籤格式 | P1 |
| 14.8 | `record()` — `transcribe=True` → `"true"`（小寫）| XML 布林值正確 | P1 |
| 14.9 | `dial()` — 有 `number` 時含 `<Number>` 子元素 | 子元素正確 | P1 |
| 14.10 | `dial()` — 無 `number` 時只有 `<Dial>` | 可用於匿名轉接 | P1 |
| 14.11 | `dial()` — `record="false"`（字串，非布林）| Twilio 期望字串 | P1 |
| 14.12 | `hangup()` — 回傳 `<Hangup/>` | 自閉合標籤 | P0 |
| 14.13 | `to_xml()` — 包裝 `<?xml version="1.0" encoding="UTF-8"?><Response>...</Response>` | XML 文件格式正確 | P0 |
| 14.14 | `to_xml()` — 空 elements 時仍產生有效 XML | `<Response></Response>` | P1 |
| 14.15 | TwiML 作為 HTTP 200 body 回傳 — `Content-Type: application/xml` | Twilio Webhook 合規 | P0 |
| 14.16 | SSML 注入防護 — 含有惡意 SSML 標記時應被轉義 | 安全驗收 | P0 |

---

### 領域 15：資料庫 Schema（Phase Voice 新表）

**組件**：`voice_calls`、`voice_dtmf_inputs`、`ivr_flows`、`voice_emotion_history`、`voice_caller_mappings`、users 擴展

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 15.1 | `voice_calls` — `call_id VARCHAR(64) UNIQUE` 約束 | 同一 `call_sid` 不可重複 | P0 |
| 15.2 | `voice_calls` — `unified_user_id` 外鍵約束（可 NULL）| 無效 UUID 不可寫入 | P0 |
| 15.3 | `voice_calls` — `caller_number` VARCHAR(20) 長度限制 | 國際號碼（最長 16 碼）足夠 | P1 |
| 15.4 | `voice_calls` — `direction` 限制 `inbound`/`outbound` | 枚舉完整性 | P1 |
| 15.5 | `voice_calls` — `end_reason` 限制 5 種值 | 枚舉完整性 | P1 |
| 15.6 | `voice_calls` — `started_at` 預設 `NOW()` | 自動時間戳記 | P1 |
| 15.7 | `voice_calls` — `duration_seconds` 在 `ended_at` 之後才可計算 | 業務邏輯正確 | P1 |
| 15.8 | `voice_calls` — 複合索引 `idx_voice_calls_user`（`unified_user_id`）| 常見查詢最佳化 | P2 |
| 15.9 | `voice_calls` — 索引 `idx_voice_calls_started`（`started_at` DESC）| 時序查詢最佳化 | P2 |
| 15.10 | `voice_dtmf_inputs` — `digit VARCHAR(8)` 支援 `0-9`, `*`, `#` | 字元集完整 | P1 |
| 15.11 | `voice_dtmf_inputs` — `call_id` 外鍵約束 | 無效 `call_id` 不可寫入 | P0 |
| 15.12 | `voice_dtmf_inputs` — `ivr_node_id` 記錄按鍵時所在節點 | IVR 流程追蹤 | P2 |
| 15.13 | `ivr_flows` — `nodes JSONB` 完整性約束 | 序列化的 JSON 為有效 IVRFlow | P1 |
| 15.14 | `ivr_flows` — `UNIQUE(flow_id, version)` 約束 | 版本唯一性 | P0 |
| 15.15 | `ivr_flows` — `is_active` 部分索引（WHERE is_active=TRUE）| active flow 查詢效能 | P2 |
| 15.16 | `ivr_flows` — `created_by` 外鍵約束（可 NULL）| 操作審計 | P2 |
| 15.17 | `voice_emotion_history` — 所有聲學特徵欄位正確 | pitch/energy/speech_rate/silence_ratio FLOAT | P1 |
| 15.18 | `voice_emotion_history` — `call_id` 外鍵約束 | 無效 `call_id` 不可寫入 | P0 |
| 15.19 | `voice_emotion_history` — `emotion_category` VARCHAR(20) | 情緒分類字串儲存 | P1 |
| 15.20 | `voice_caller_mappings` — `raw_caller_number UNIQUE` | 原始號碼唯一 | P0 |
| 15.21 | `voice_caller_mappings` — `anonymized_number` 唯一約束 | 脫敏號碼也唯一 | P1 |
| 15.22 | `voice_caller_mappings` — `unified_user_id` 外鍵約束（可 NULL）| 未匹配時可為 NULL | P1 |
| 15.23 | `users` 表 — 新增 `voice_pin_hash VARCHAR(255)` 可 NULL | 不影響既有用戶 | P0 |
| 15.24 | `users` 表 — `voice_pin_hash` 欄位修改為 `argon2` hash（不可逆）| 密碼安全儲存 | P0 |
| 15.25 | Schema Migration — 所有新表可 `CREATE TABLE` 成功 | 遷移腳本正確 | P0 |
| 15.26 | Schema Migration — 既有 `users` 表 `ALTER TABLE` 不影響現有用戶 | 向後相容 | P0 |

---

### 領域 16：Prometheus Metrics（Phase Voice 新增）

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 16.1 | `omnibot_voice_calls_total` — counter，label `direction` | inbound/outbound 計數正確 | P0 |
| 16.2 | `omnibot_voice_calls_total` — label `end_reason` | completed/transferred/no_answer/failed/abandoned | P0 |
| 16.3 | `omnibot_voice_calls_total` — 來話建立時 +1 | Counter increment 正確 | P0 |
| 16.4 | `omnibot_voice_call_duration_seconds` — histogram buckets `[30, 60, 120, 180, 240, 300]` | 通話時長分佈正確 | P1 |
| 16.5 | `omnibot_voice_call_duration_seconds` — 通話結束時記錄 | Duration recording 正確 | P0 |
| 16.6 | `omnibot_voice_ivr_completion_ratio` — gauge，`completed / total` | IVR 完成率計算正確 | P1 |
| 16.7 | `omnibot_voice_asr_errors_total` — counter，label `provider` | whisper/google 錯誤分開計數 | P0 |
| 16.8 | `omnibot_voice_asr_errors_total` — ASR 失敗時 +1 | 錯誤追蹤正確 | P0 |
| 16.9 | `omnibot_voice_tts_errors_total` — counter，label `provider` | TTS 錯誤追蹤 | P0 |
| 16.10 | `omnibot_voice_tts_errors_total` — TTS 失敗時 +1 | 錯誤追蹤正確 | P0 |
| 16.11 | `omnibot_voice_emotion_escalations_total` — counter，label `reason` | 情緒觸發轉接計數 | P0 |
| 16.12 | `omnibot_voice_emotion_escalations_total` — 觸發時 +1 | 觸發追蹤正確 | P0 |
| 16.13 | `omnibot_voice_dtmf_inputs_total` — counter，label `digit` | 按鍵分佈追蹤 | P1 |
| 16.14 | `omnibot_voice_dtmf_inputs_total` — DTMF 輸入時 +1 | 計數正確 | P1 |
| 16.15 | Prometheus endpoint — `/metrics` 包含所有 `omnibot_voice_*` metrics | 端點正確暴露 | P0 |
| 16.16 | Metrics 重啟後歸零 — Counter 不持久化，Prometheus 端重啟後從 0 開始 | 行為預期正確 | P1 |
| 16.17 | Grafana Dashboard — 7 個 Panels 對應查詢正確 | Dashboard query 驗證 | P2 |

---

### 領域 17：既有系統整合斷言驗證

**組件**：Phase 1-3 既有模組，`SPEC/omnibot-phase-voice.md` 斷言

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 17.1 | `Platform` enum — 新增 `VOICE = "voice"` 後既有分支不受影響 | `if platform == Platform.LINE` 行為不變 | P0 |
| 17.2 | `UnifiedMessage` — `platform=VOICE` 可正常建立 | 枚舉值正確，格式相容 | P0 |
| 17.3 | `HybridKnowledgeLayer.query()` — 接收 `platform=VOICE` 的 `UnifiedMessage` | Layer 1-4 處理管線不崩潰 | P0 |
| 17.4 | `InputSanitizer.sanitize()` — ASR transcript 通過文字清理 | 字元正規化正常 | P0 |
| 17.5 | `PIIMasking` — 來電號碼在 Telecom Adapter 已脫敏 | 雙重脫敏防護 | P1 |
| 17.6 | `EmotionAnalyzer`（Phase 2 文字）— 接收 IVR COLLECT 節點的文字輸入 | 文字情緒分析正常運作 | P0 |
| 17.7 | `IntentRouter + DST` — 接收 IVR 餽給的文字，輸出意圖 | DST 狀態追蹤正常 | P0 |
| 17.8 | `EscalationManager` — `IVREngine` TRANSFER 節點觸發時正確呼叫 | Layer 4 轉接正常 | P0 |
| 17.9 | `conversations` 表 — `platform=VOICE` 的對話記錄正常寫入 | conversations table 相容 | P0 |
| 17.10 | `messages` 表 — voice 平台訊息正常寫入 | messages table 相容 | P0 |
| 17.11 | Redis Streams (`AsyncMessageProcessor`) — voice queue 訊息處理 | Phase 3 Redis Streams 復用 | P0 |
| 17.12 | Structured Logger — voice 事件寫入結構化日誌 | JSON 日誌格式不變 | P0 |
| 17.13 | `ResponseGenerator` — 回傳 `UnifiedResponse`，`VoicePlatformAdapter.response_to_voice()` 轉換 | 回覆格式鏈正確 | P0 |
| 17.14 | 斷言：Layer 1-4 處理管線完全不知道也不需要知道輸入來自哪個 platform | 平台無感知架構正確 | P0 |

---

### 領域 18：部署驗證

**組件**：Docker Compose、Twilio Console、環境變數

| # | 測試項目 | 測試目標 | 優先 |
|---|---------|---------|------|
| 18.1 | Docker Compose — `whisper-asr` service 啟動成功 | Container 正常運行 | P0 |
| 18.2 | Docker Compose — `whisper-asr` port 9000 暴露 | `localhost:9000` 可存取 | P0 |
| 18.3 | Docker Compose — `whisper-asr` GPU reservation (`nvidia`) | GPU 資源正確配置 | P1 |
| 18.4 | Docker Compose — `whisper-asr` `models` volume mount | 模型檔案持久化 | P2 |
| 18.5 | Docker Compose — `omnibot-api` 環境變數 `VOICE_ENABLED=true` | Phase Voice 功能開關正確 | P0 |
| 18.6 | Docker Compose — `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` 注入 | 敏感性資料不寫入 image | P0 |
| 18.7 | Docker Compose — `ASR_API_URL=http://whisper-asr:9000` | 容器間網路正確 | P0 |
| 18.8 | Docker Compose — `whisper-asr` 記憶體限制（避免 OOM）| Resource limits 設定 | P2 |
| 18.9 | Twilio Console — Webhook URL 設定為 `https://omnibot.example.com/api/v1/voice/webhook/twilio/incoming` | URL 格式正確 | P0 |
| 18.10 | Twilio Console — Status Callback URL 設定正確 | 通話狀態回調正常 | P0 |
| 18.11 | Twilio Console — ASR 引擎選擇 Whisper（本地）| Twilio ASR 設定驗證 | P1 |
| 18.12 | Twilio Console — TTS 引擎選擇 Google Cloud TTS | Twilio TTS 設定驗證 | P1 |
| 18.13 | 環境變數缺失 — `VOICE_ENABLED` 未設定時，Phase Voice 功能應關閉 | Feature flag 正確處理 | P0 |
| 18.14 | 環境變數缺失 — `TWILIO_AUTH_TOKEN` 未設定時，Webhook 驗證失敗 | 安全 fail-secure | P0 |
| 18.15 | TLS 終結 — Twilio 要求 HTTPS Webhook URL | 生產環境 HTTPS 必要 | P0 |

---

### 領域 19：驗收標準 SQL 查詢

**目標**：以 SQL 查詢驗證 Phase Voice 上線後各項 KPI 是否達標

| # | 測試項目 | SQL 查詢（示意） | 優先 |
|---|---------|----------------|------|
| 19.1 | 語音 FCR >= 70% | `SELECT ... FROM conversations WHERE platform='voice' AND status='resolved' AND source != 'escalate'` | P0 |
| 19.2 | IVR 完成率 >= 80% | `SELECT COUNT(*) WHERE end_reason='completed' / total` | P0 |
| 19.3 | 平均通話時長 < 4 分鐘（240 秒）| `SELECT AVG(duration_seconds) FROM voice_calls WHERE ended_at IS NOT NULL` | P0 |
| 19.4 | ASR WER < 10%（需人工抽樣校對）| 人工校對流程（不自動）| P1 |
| 19.5 | 來話接通率 >= 98% | `SELECT COUNT(*) WHERE status IN ('answered','completed') / total` | P0 |
| 19.6 | Rate Limit 命中率 > 0 | `SELECT omnibot_voice_rate_limited_total FROM Prometheus` | P1 |
| 19.7 | 情緒轉接觸發 > 0 | `SELECT omnibot_voice_emotion_escalations_total FROM Prometheus` | P1 |
| 19.8 | `voice_calls` 表記錄完整性 — 所有來話都有對應記錄 | Twilio 來話數 ≈ `SELECT COUNT(*) FROM voice_calls` | P0 |
| 19.9 | `voice_dtmf_inputs` 表記錄 — DTMF 輸入有記錄 | DTMF 按鍵有記錄 | P1 |
| 19.10 | IVR 版本 — 啟用中的 Flow 版本可查詢 | `SELECT nodes FROM ivr_flows WHERE is_active=TRUE` | P1 |

---

### 領域 20：錯誤碼覆蓋

**組件**：Phase Voice 新增錯誤碼，所有錯誤碼 HTTP 行為

| # | 測試項目 | 預期行為 | 優先 |
|---|---------|---------|------|
| 20.1 | `VOICE_CALL_FAILED (500)` — 來話處理失敗 | HTTP 500，日誌記錄 error | P0 |
| 20.2 | `VOICE_ASR_ERROR (500)` — ASR 轉文字失敗 | HTTP 500，IVR 流程中斷處理 | P0 |
| 20.3 | `VOICE_TTS_ERROR (500)` — TTS 合成失敗 | HTTP 500，IVR 流程中斷處理 | P0 |
| 20.4 | `VOICE_NO_ANSWER (200)` — 來話未接聽 | HTTP 200，`voice_calls.end_reason='no_answer'` | P0 |
| 20.5 | `VOICE_IVR_TIMEOUT (200)` — IVR 無輸入超時 | HTTP 200，`voice_calls.end_reason='no_answer'` | P0 |
| 20.6 | `VOICE_DTMF_INVALID (200)` — DTMF 無效按鍵 | HTTP 200，重新播放 MENU | P0 |
| 20.7 | `VOICE_RATE_LIMITED (429)` — 超出來話頻率限制 | HTTP 429，回傳 TwiML 告知無法接通 | P0 |
| 20.8 | 既有錯誤碼 — Phase 1-3 的 8 個錯誤碼不受影響 | `AUTH_INVALID_SIGNATURE` 等仍正常運作 | P0 |
| 20.9 | 錯誤回應格式 — `{"error": "VOICE_XXX", "message": "..."}` | 錯誤格式一致性 | P1 |
| 20.10 | 錯誤不回傳內部實作細節 — stack trace 不在 HTTP body | 安全 fail-secure | P0 |

---

## 測試案例數量彙總

| 領域 | 測試案例數 | P0 數量 | P1 數量 | P2 數量 |
|------|-----------|--------|--------|--------|
| 1. Twilio Webhook 接收與驗證 | 15 | 8 | 6 | 1 |
| 2. 電話號碼脫敏 | 8 | 4 | 4 | 0 |
| 3. VoicePlatformAdapter | 10 | 7 | 3 | 0 |
| 4. IVR 流程定義 | 15 | 5 | 9 | 1 |
| 5. IVR Engine — 節點執行 | 14 | 8 | 5 | 1 |
| 6. IVR Engine — 路由邏輯 | 14 | 9 | 5 | 0 |
| 7. IVR Flow 管理 API | 10 | 5 | 4 | 1 |
| 8. ASR Adapter | 13 | 7 | 5 | 1 |
| 9. TTS Adapter | 13 | 5 | 7 | 1 |
| 10. Voice Emotion Analyzer | 17 | 11 | 5 | 1 |
| 11. Voice Authenticator | 13 | 7 | 6 | 0 |
| 12. Voice Call Orchestrator | 13 | 9 | 3 | 1 |
| 13. Voice Rate Limiter | 12 | 7 | 5 | 0 |
| 14. TwiML 回應建構 | 16 | 8 | 8 | 0 |
| 15. 資料庫 Schema | 26 | 11 | 10 | 5 |
| 16. Prometheus Metrics | 17 | 9 | 6 | 2 |
| 17. 既有系統整合斷言 | 14 | 12 | 2 | 0 |
| 18. 部署驗證 | 15 | 7 | 4 | 4 |
| 19. 驗收標準 SQL | 10 | 6 | 4 | 0 |
| 20. 錯誤碼覆蓋 | 10 | 8 | 2 | 0 |
| **總計** | **275** | **153** | **103** | **19** |

---

## 測試執行優先順序建議

### Sprint 1（核心路徑）
1. `TwilioAdapter` 驗證 + Webhook 端點
2. `IVRFlow` 資料結構
3. `IVREngine`（start + execute_node + handle_input）
4. `ASRAdapter` + `TTSAdapter`
5. `TwiMLResponse` 全部方法
6. `voice_calls` Schema

### Sprint 2（主要功能）
7. `VoicePlatformAdapter`
8. `VoiceCallOrchestrator`
9. `VoiceRateLimiter`
10. `VoiceAuthenticator`
11. `voice_dtmf_inputs` Schema
12. Prometheus metrics 埋點

### Sprint 3（完整覆蓋）
13. `VoiceEmotionAnalyzer`
14. `ivr_flows` 管理 API
15. `voice_emotion_history` + `voice_caller_mappings` Schema
16. 既有系統整合斷言驗證
17. 部署驗證
18. 錯誤碼覆蓋
19. 驗收標準 SQL 查詢
20. SSMLBuilder

---

*文件版本: v1.0*  
*對應規格: `SPEC/omnibot-phase-voice.md`*  
*最後更新: 2026-05-01*
