# OmniBot TDD 驗證清單

> 依據 `omnibot-phase-1.md`、`omnibot-phase-2.md`、`omnibot-phase-3.md` (v7.0) 產生
> 每個條目對應一個 test case，遵循 RED-GREEN-REFACTOR 原則

---

## Phase 1: MVP 基礎

### 1. Webhook 簽名驗證

- [ ] `test_webhook_line_signature_valid`: LINE secret 正確時 `verify()` 回傳 True
- [ ] `test_webhook_line_signature_invalid`: LINE secret 錯誤時 `verify()` 回傳 False（使用 `hmac.compare_digest` 防時序攻擊）
- [ ] `test_webhook_telegram_signature_valid`: Telegram bot token 正確時 `verify()` 回傳 True
- [ ] `test_webhook_telegram_signature_invalid`: Telegram signature 錯誤時回傳 False
- [ ] `test_webhook_verifier_registry_resolves_correct_type`: `VERIFIERS["line"]` 解析為 `LineWebhookVerifier`，`VERIFIERS["telegram"]` 解析為 `TelegramWebhookVerifier`
- [ ] `test_webhook_401_on_invalid_signature`: POST `/api/v1/webhook/line` 帶錯誤簽名時回傳 401 + `AUTH_INVALID_SIGNATURE`
- [ ] `test_webhook_429_on_rate_limit_exceeded`: 超過 Rate Limit 時回傳 429 + `RATE_LIMIT_EXCEEDED`

### 2. 統一消息格式

- [ ] `test_unified_message_immutable`: `UnifiedMessage` 實例化後修改欄位會拋 `FrozenInstanceError`
- [ ] `test_unified_message_default_received_at`: 未傳 `received_at` 時自動設定為 UTC now
- [ ] `test_unified_message_reply_token_none_for_telegram`: Platform=TELEGRAM 時 `reply_token` 為 None
- [ ] `test_unified_message_reply_token_set_for_line`: Platform=LINE 且有 reply_token 時正確保存
- [ ] `test_unified_response_fields`: `UnifiedResponse` 包含 `content`, `source`, `confidence`, `knowledge_id`, `emotion_adjustment`

### 3. 統一回應格式

- [ ] `test_api_response_success_true_no_error`: `ApiResponse(success=True, data=X)` 時 `error` 為 None
- [ ] `test_api_response_success_false_has_error`: `ApiResponse(success=False, error="msg")` 時 `error_code` 可設定
- [ ] `test_paginated_response_defaults`: `PaginatedResponse` 的 `total=0`, `page=1`, `limit=20`, `has_next=False`
- [ ] `test_paginated_response_has_next_true`: 當總數超過 page*limit 時 `has_next=True`

### 4. 輸入清理 L2

- [ ] `test_sanitizer_nfkc_normalization_全形轉半形`: 全形文字經 `sanitize()` 轉為半形
- [ ] `test_sanitizer_removes_control_characters`: 控制字元（\x00-\x1F 除了 \n\t）被移除
- [ ] `test_sanitizer_preserves_newline_and_tab`: `\n` 和 `\t` 保留
- [ ] `test_sanitizer_trims_whitespace`: 前後空白被 strip
- [ ] `test_sanitizer_preserves_printable`: 一般可列印字元保留

### 5. 基礎 PII 去識別化 L4

- [ ] `test_pii_mask_phone_台灣格式_0912_123_456`: 電話 `0912-123-456` 被遮蔽為 `[phone_masked]`
- [ ] `test_pii_mask_phone_10digits`: 10 位數電話 `0912345678` 被遮蔽
- [ ] `test_pii_mask_email`: `test@example.com` 被遮蔽為 `[email_masked]`
- [ ] `test_pii_mask_address_台北市`: 含「台北市」的路/街/巷/弄/號 被遮蔽
- [ ] `test_pii_mask_address_高雄市`: 含「高雄市」的路/街/巷/弄/號 被遮蔽
- [ ] `test_pii_mask_multiple_occurrences`: 同一 PII 類型出現多次時全部遮蔽，`mask_count` 正確
- [ ] `test_pii_mask_returns_pii_types`: 回傳的 `pii_types` list 包含被偵測到的類型
- [ ] `test_pii_should_escalate_sensitive_keyword_密碼`: 內文含「密碼」時 `should_escalate()` 回傳 True
- [ ] `test_pii_should_escalate_sensitive_keyword_銀行帳戶`: 內文含「銀行帳戶」時回傳 True
- [ ] `test_pii_should_escalate_negative`: 不含敏感關鍵字時回傳 False
- [ ] `test_pii_mask_no_double_replacement`: 從後往前replace避免offset錯誤

### 6. 速率限制

- [ ] `test_token_bucket_initial_full`: 新 TokenBucket 初始 tokens == capacity
- [ ] `test_token_bucket_consume_decrements`: `consume(1)` 後 tokens 減 1
- [ ] `test_token_bucket_consume_returns_true_when_tokens_available`: tokens > 0 時回傳 True
- [ ] `test_token_bucket_consume_returns_false_when_empty`: tokens == 0 時回傳 False
- [ ] `test_token_bucket_refill`: 經過 time 後 tokens 回補
- [ ] `test_token_bucket_capped_at_capacity`: tokens 補充不超過 capacity
- [ ] `test_rate_limiter_per_user_isolation`: `platform:user1` 和 `platform:user2` 的 bucket 獨立
- [ ] `test_rate_limiter_creates_bucket_on_first_check`: 首次 `check()` 時自動建立新 bucket

### 7. Knowledge Layer Phase 1（規則匹配）

- [ ] `test_knowledge_layer_rule_match_exact_question`: 查詢完全匹配 `question` 時 confidence = 0.95
- [ ] `test_knowledge_layer_rule_match_keyword`: 查詢匹配 keywords 時 confidence = 0.7
- [ ] `test_knowledge_layer_rule_match_ilike_partial`: `ILIKE %query%` 模糊匹配正常
- [ ] `test_knowledge_layer_rule_match_orders_by_version_desc`: 同 question 多版本時取 version 最高
- [ ] `test_knowledge_layer_rule_match_limit_5`: 最多回傳 5 筆結果
- [ ] `test_knowledge_layer_rule_match_inactive_excluded`: `is_active = FALSE` 的條目被排除
- [ ] `test_knowledge_layer_no_match_confidence_below_0.7`: confidence <= 0.7 時不採用規則匹配結果
- [ ] `test_knowledge_layer_escalate_when_no_match`: 無匹配時回傳 `KnowledgeResult(id=-1, source="escalate")`
- [ ] `test_knowledge_result_id_minus_one_means_escalate`: `id = -1` 明確代表轉接（非知識庫來源）

### 8. 基礎人工轉接（無 SLA）

- [ ] `test_basic_escalation_create_inserts_row`: `create()` 回傳新 escalation_queue 的 id
- [ ] `test_basic_escalation_assign_sets_agent_and_picked_at`: `assign()` 更新 `assigned_agent` 和 `picked_at`
- [ ] `test_basic_escalation_assign_only_unresolved`: 已 `resolved_at` 的記錄不被 `assign()` 影響
- [ ] `test_basic_escalation_resolve_sets_resolved_at`: `resolve()` 設定 `resolved_at` 時間戳

### 9. 結構化日誌

- [ ] `test_structured_logger_output_is_json`: `log()` 輸出的 `entry` 為合法 JSON
- [ ] `test_structured_logger_includes_timestamp`: JSON 包含 ISO format `timestamp` 欄位（結尾 Z）
- [ ] `test_structured_logger_includes_level`: JSON 包含 `level` 欄位
- [ ] `test_structured_logger_includes_service_name`: JSON 包含 `service` 欄位
- [ ] `test_structured_logger_includes_message`: JSON 包含 `message` 欄位
- [ ] `test_structured_logger_extra_fields_passed_as_kwargs`:額外 `kwargs` 展開為 JSON 頂層欄位
- [ ] `test_structured_logger_info_alias_calls_log_with_INFO`: `info()` 等同 `log("INFO", ...)`
- [ ] `test_structured_logger_error_alias_calls_log_with_ERROR`: `error()` 等同 `log("ERROR", ...)`

### 10. 健康檢查端點

- [ ] `test_health_endpoint_returns_200`: GET `/api/v1/health` 回傳 200
- [ ] `test_health_endpoint_includes_postgres_status`: 回應包含 `postgres: true/false`
- [ ] `test_health_endpoint_includes_redis_status`: 回應包含 `redis: true/false`
- [ ] `test_health_endpoint_includes_uptime_seconds`: 回應包含 `uptime_seconds: float`
- [ ] `test_health_endpoint_status_healthy_when_all_healthy`: 所有元件 healthy 時 `status = "healthy"`
- [ ] `test_health_endpoint_status_degraded_when_one_down`: 任一元件失敗時 `status = "degraded"`

### 11. 知識庫管理 API

- [ ] `test_knowledge_create_returns_api_response`: POST `/api/v1/knowledge` 回傳 `ApiResponse`
- [ ] `test_knowledge_get_with_pagination`: GET `/api/v1/knowledge?q=xx&page=1&limit=20` 分頁正常
- [ ] `test_knowledge_get_limit_max_100`: `limit > 100` 時取至 100
- [ ] `test_knowledge_get_returns_paginated_response`: 回傳 `PaginatedResponse` 含 `total`, `page`, `has_next`
- [ ] `test_knowledge_update`: PUT `/api/v1/knowledge/{id}` 可更新知識條目
- [ ] `test_knowledge_delete`: DELETE `/api/v1/knowledge/{id}` 可刪除（軟刪除 `is_active=FALSE`）
- [ ] `test_knowledge_bulk_import`: POST `/api/v1/knowledge/bulk` 批次匯入多筆
- [ ] `test_knowledge_not_found_returns_404`: GET 不存在的 id 回傳 404 + `KNOWLEDGE_NOT_FOUND`
- [ ] `test_validation_error_returns_422`: 請求參數驗證失敗時回傳 422 + `VALIDATION_ERROR`

### 12. 對話記錄 API

- [ ] `test_conversations_list_returns_api_response`: GET `/api/v1/conversations` 回傳列表

### 13. Database Schema

- [ ] `test_users_table_uniqueness_constraint`: 同一 `(platform, platform_user_id)` 不可重複
- [ ] `test_users_unified_user_id_is_uuid`: `unified_user_id` 為有效 UUID
- [ ] `test_conversations_foreign_key_to_users`: `conversations.unified_user_id` 外鍵參考 `users.unified_user_id`
- [ ] `test_messages_foreign_key_to_conversations`: `messages.conversation_id` 外鍵參考 `conversations.id`
- [ ] `test_knowledge_base_embeddings_vector_384`: `embeddings` 欄位維度為 384（對齊 MiniLM-L12 輸出）
- [ ] `test_escalation_queue_conversation_id_unique`: `escalation_queue.conversation_id` 為 UNIQUE（每對話僅一筆轉接）
- [ ] `test_security_logs_layer_values`: `layer` 僅接受 L0/L1/L2/L3/L4/L5
- [ ] `test_user_feedback_check_constraint`: `feedback` 僅接受 `thumbs_up` / `thumbs_down`

---

## Phase 2: 智慧化 + 安全強化

### 14. Webhook 簽名驗證 Phase 2（Messenger + WhatsApp）

- [ ] `test_webhook_messenger_signature_valid`: `MessengerWebhookVerifier` 正確驗證 `sha256=` 前綴 signature
- [ ] `test_webhook_messenger_signature_invalid`: 錯誤 signature 時回傳 False
- [ ] `test_webhook_whatsapp_signature_valid`: `WhatsAppWebhookVerifier` 正確驗證
- [ ] `test_webhook_whatsapp_signature_invalid`: 錯誤 signature 時回傳 False
- [ ] `test_verifier_registry_includes_messenger_and_whatsapp`: Phase 2 後 `VERIFIERS` 包含全部 4 平台

### 15. Prompt Injection Defense L3

- [ ] `test_prompt_injection_detects_ignore_instructions`: 包含 "ignore previous instructions" 時 `is_safe=False`
- [ ] `test_prompt_injection_detects_system_colon`: 包含 "system:" 時被阻擋
- [ ] `test_prompt_injection_detects_pretend_instructions`: 包含 "pretend you are" 時被阻擋
- [ ] `test_prompt_injection_detects_new_instructions`: 包含 "new instructions:" 時被阻擋
- [ ] `test_prompt_injection_detects_override_keyword`: 包含 "override your" 時被阻擋
- [ ] `test_prompt_injection_detects_disregard_keyword`: 包含 "disregard previous" 時被阻擋
- [ ] `test_prompt_injection_case_insensitive`: Pattern matching 不分大小寫
- [ ] `test_prompt_injection_safe_input_returns_is_safe_true`: 正常輸入 `is_safe=True`
- [ ] `test_prompt_injection_normalizes_before_check`: NFKC 正規化後再偵測
- [ ] `test_sandwich_prompt_structure`: `build_sandwich_prompt()` 輸出包含 `[SYSTEM INSTRUCTION]`, `[RETRIEVED CONTEXT]`, `[USER MESSAGE]`, `[SYSTEM REMINDER]`
- [ ] `test_sandwich_prompt_system_instruction_first`: 系統指令在最前面，優先級最高
- [ ] `test_security_check_result_blocked_reason_included`: `SecurityCheckResult` 含 `blocked_reason` 與 `risk_level`

### 16. PII 去識別化 L4 Phase 2（信用卡 + Luhn）

- [ ] `test_pii_mask_credit_card_valid_16digits`: 16 碼信用卡格式（空號/連號）被偵測但不遮蔽（需 Luhn）
- [ ] `test_pii_mask_credit_card_luhn_valid`: 通過 Luhn 校驗的信用卡被遮蔽為 `[credit_card_masked]`
- [ ] `test_pii_mask_credit_card_luhn_invalid`: Luhn 校驗失敗的 16 碼數字**不**被遮蔽（False Positive 防止）
- [ ] `test_pii_mask_credit_card_with_spaces`: `1234 5678 9012 3456` 格式正確遮蔽
- [ ] `test_pii_mask_credit_card_with_dashes`: `1234-5678-9012-3456` 格式正確遮蔽
- [ ] `test_pii_luhn_check_known_valid_number`: 已知有效卡號（4532015112830366）通過 Luhn
- [ ] `test_pii_luhn_check_known_invalid_number`: 已知無效卡號通過 Luhn 時回傳 False
- [ ] `test_pii_mask_combined_with_phase1_types`: 電話 + Email + 信用卡同時存在時全部遮蔽
- [ ] `test_pii_mask_result_pii_types_contains_credit_card`: 遮蔽信用卡後 `pii_types` 含 `"credit_card"`

### 17. Hybrid Knowledge Layer V7（Layer 1 + 2 + 3 + 4）

- [ ] `test_hybrid_layer_rule_match_confidence_above_0.9`: Layer 1 confidence > 0.9 時直接採用，回傳 `source="rule"`
- [ ] `test_hybrid_layer_rrf_fusion_combines_rule_and_rag`: RRF k=60 融合 rule_results + rag_results
- [ ] `test_hybrid_layer_rrf_scores_ranked_correctly`: rank 1 的文件 RRF 分數最高
- [ ] `test_hybrid_layer_rrf_respects_k_parameter`: k=60 時 `1/(rank+60)` 計算分數
- [ ] `test_hybrid_layer_rag_search_uses_embedding_model_filter`: RAG 查詢時過濾 `embedding_model` 欄位
- [ ] `test_hybrid_layer_rag_search_orders_by_cosine_similarity`: 向量搜尋以 `embeddings <=> query_embedding` 排序
- [ ] `test_hybrid_layer_llm_generate_returns_result_when_overridden`: HybridKnowledgeLayer 子類 override `_llm_generate()` 並回傳 `KnowledgeResult` 時，hybrid 結果採用該 layer 的回覆（`source="llm"`）
- [ ] `test_hybrid_layer_llm_generate_returns_none_falls_through_to_layer4`: 子類 `_llm_generate()` 回傳 `None` 時，hybrid 繼續往 Layer 4（escalate）遞進，不阻斷流程
- [ ] `test_hybrid_layer_escalate_when_all_layers_fail`: 三層都無結果時回傳 `source="escalate"`, `id=-1`
- [ ] `test_hybrid_layer_returns_knowledge_result_with_correct_source`: 各層回傳的 `source` 符合預期（rule/rag/wiki/escalate）

### 18. DST 對話狀態機

- [ ] `test_dialogue_state_idle_to_intent_detected`: IDLE 收到訊息後轉為 INTENT_DETECTED
- [ ] `test_dialogue_state_intent_detected_all_slots_filled_to_processing`: 所有 required slot 已填時轉 PROCESSING
- [ ] `test_dialogue_state_intent_detected_missing_slot_to_slot_filling`: 缺少 slot 時轉 SLOT_FILLING
- [ ] `test_dialogue_state_slot_filling_complete_to_awaiting_confirmation`: 所有 slot 填完後轉 AWAITING_CONFIRMATION
- [ ] `test_dialogue_state_slot_filling_3_turns_exceeded_to_escalated`: SLOT_FILLING 超過 3 輪未完成時轉 ESCALATED
- [ ] `test_dialogue_state_awaiting_confirmation_confirm_to_processing`: 用戶確認後轉 PROCESSING
- [ ] `test_dialogue_state_awaiting_confirmation_deny_to_slot_filling`: 用戶否認後回到 SLOT_FILLING
- [ ] `test_dialogue_state_processing_success_to_resolved`: 成功回覆後轉 RESOLVED
- [ ] `test_dialogue_state_processing_low_confidence_to_escalated`: confidence < 0.65 時轉 ESCALATED
- [ ] `test_dialogue_state_escalated_to_resolved_on_human_intervention`: 人工介入後轉 RESOLVED
- [ ] `test_dialogue_state_immutable_transition`: `transition()` 回傳新 instance，原 instance 不變
- [ ] `test_dialogue_state_turn_count_increments_on_transition`: 每次 transition `turn_count + 1`
- [ ] `test_dialogue_state_missing_slots_returns_required_empty`: 全部 slot 已填時 `missing_slots()` 回傳空 list
- [ ] `test_dialogue_state_missing_slots_returns_unfilled_required`: 有未填 required slot 時回傳該 slot 清單

### 19. 統一情緒模組

- [ ] `test_emotion_tracker_add_score`: `add()` 可新增 EmotionScore 至 history
- [ ] `test_emotion_tracker_weighted_score_positive_decay`: 新近 positive 情緒對加權分數貢獻更高
- [ ] `test_emotion_tracker_weighted_score_negative_decay`: 24 小時前的 negative 情緒權重衰減至約 50%
- [ ] `test_emotion_tracker_half_life_24h`: `half_life_hours=24` 時，符合指數衰減公式
- [ ] `test_emotion_tracker_consecutive_negative_count_3`: 連續 3 次 negative 時 `consecutive_negative_count() == 3`
- [ ] `test_emotion_tracker_consecutive_negative_resets_on_positive`: 2 次 negative 後一次 positive，下次 negative count 重置為 1
- [ ] `test_emotion_tracker_should_escalate_true_at_3_consecutive_negative`: 連續 3 次 negative 時 `should_escalate() == True`
- [ ] `test_emotion_tracker_should_escalate_false_at_2_consecutive_negative`: 連續 2 次 negative 時 `should_escalate() == False`
- [ ] `test_emotion_tracker_current_weighted_score_empty_history`: 空 history 時回傳 0.0
- [ ] `test_emotion_score_category_enum`: `category` 僅接受 POSITIVE / NEUTRAL / NEGATIVE

### 20. Grounding Checks L5

- [ ] `test_grounding_check_grounded_above_threshold`: similarity >= 0.75 時 `grounded=True`
- [ ] `test_grounding_check_not_grounded_below_threshold`: similarity < 0.75 時 `grounded=False`
- [ ] `test_grounding_check_returns_best_match_index`: 正確回傳 `best_match_index`
- [ ] `test_grounding_check_no_source_text_returns_false`: 空 `source_texts` 時 `grounded=False`
- [ ] `test_grounding_check_returns_score`: 回傳 `score` 欄位含相似度分數
- [ ] `test_grounding_check_threshold_configurable`: Threshold 可在 constructor 傳入自訂值
- [ ] `test_grounding_check_uses_correct_embedding_model`: 預設使用 `paraphrase-multilingual-MiniLM-L12-v2`

### 21. 人工轉接 + SLA Phase 2

- [ ] `test_escalation_manager_sla_normal_30_minutes`: priority=0 時 SLA deadline 為 now+30min
- [ ] `test_escalation_manager_sla_high_15_minutes`: priority=1 時 SLA deadline 為 now+15min
- [ ] `test_escalation_manager_sla_urgent_5_minutes`: priority=2（emotion_trigger）時 SLA deadline 為 now+5min
- [ ] `test_escalation_manager_create_returns_id`: `create()` 回傳新 escalation_queue id
- [ ] `test_escalation_manager_assign`: `assign()` 設定 `assigned_agent` 和 `picked_at`
- [ ] `test_escalation_manager_resolve_sets_resolved_at`: `resolve()` 設定 `resolved_at`
- [ ] `test_escalation_manager_get_sla_breaches`: `get_sla_breaches()` 回傳 `sla_deadline < NOW() AND resolved_at IS NULL` 的項目
- [ ] `test_escalation_manager_get_sla_breaches_ordered_by_priority`: 結果以 `priority DESC, queued_at ASC` 排序

### 22. 使用者回饋收集

- [ ] `test_feedback_thumbs_up_accepted`: `feedback='thumbs_up'` 可寫入
- [ ] `test_feedback_thumbs_down_accepted`: `feedback='thumbs_down'` 可寫入
- [ ] `test_feedback_optional_comment`: `comment` 為 optional，可為 NULL
- [ ] `test_feedback_invalid_value_rejected`: 非 `thumbs_up`/`thumbs_down` 的值被 CHECK constraint 拒絕

### 23. Redis Streams 異步處理（Phase 3 前置）

- [ ] `test_async_message_processor_ensure_group_creates_group`: `_ensure_group()` 第一次呼叫時建立消費者群組
- [ ] `test_async_message_processor_ensure_group_ignores_busygroup`: 群組已存在時不拋 `BUSYGROUP` 錯誤
- [ ] `test_async_message_processor_consume_returns_streams`: `consume()` 回傳 Redis stream 資料
- [ ] `test_async_message_processor_ack_marks_processed`: `ack()` 後訊息不再被重複處理

### 24. 指數退避重試（Phase 3 前置）

- [ ] `test_retry_exponential_backoff_doubles`: 第 2 次 retry delay ≈ base_delay * 2
- [ ] `test_retry_exponential_backoff_capped_at_max_delay`: 最大 delay 不超過 `max_delay`
- [ ] `test_retry_jitter_randomizes_delay`: jitter enabled 時 delay 有隨機性
- [ ] `test_retry_max_retries_respected`: 超過 `max_retries` 次數後不再重試，直接拋例外
- [ ] `test_retry_succeeds_on_first_attempt_no_delay`: 第一次就成功時不 sleep
- [ ] `test_retry_returns_result_on_success`: 成功時回傳函式結果

---

## Phase 3: 企業級 + Production Ready

### 25. RBAC 權限管理

- [ ] `test_rbac_admin_has_all_knowledge_permissions`: admin 角色可 read/write/delete 知識庫
- [ ] `test_rbac_editor_has_read_write_knowledge`: editor 可 read/write 但不可 delete
- [ ] `test_rbac_agent_has_read_only_knowledge`: agent 僅可 read 知識庫
- [ ] `test_rbac_auditor_has_read_only_all`: auditor 可 read 所有資源（knowledge/escalate/audit/experiment/system）
- [ ] `test_rbac_agent_cannot_write_escalate`: agent 不可 write escalate（寫入轉接佇列例外）
- [ ] `test_rbac_check_returns_true_for_allowed_action`: `check("admin", "knowledge", "write") == True`
- [ ] `test_rbac_check_returns_false_for_denied_action`: `check("agent", "knowledge", "delete") == False`
- [ ] `test_rbac_check_returns_false_for_unknown_role`: 未知 role 回傳 False
- [ ] `test_rbac_require_decorator_allows_permitted`: 有權限的 role 可執行被 `@require` 保護的函式
- [ ] `test_rbac_require_decorator_blocks_denied`: 權限不足時拋 `PermissionError`
- [ ] `test_rbac_require_raises_with_insufficient_role_error_code`: 例外訊息包含 role 與 action 資訊

### 26. 管理 API RBAC 保護

- [ ] `test_knowledge_post_requires_bearer_auth`: POST `/api/v1/knowledge` 無 Bearer Token 回傳 401
- [ ] `test_knowledge_post_requires_rbac_knowledge_write`: 無 `knowledge:write` 權限回傳 403 + `AUTHZ_INSUFFICIENT_ROLE`
- [ ] `test_knowledge_put_requires_rbac_knowledge_write`: PUT `/api/v1/knowledge/{id}` 需要 `knowledge:write`
- [ ] `test_knowledge_delete_requires_rbac_knowledge_delete`: DELETE 需要 `knowledge:delete`
- [ ] `test_experiments_post_requires_rbac_experiment_write`: POST `/api/v1/experiments` 需要 `experiment:write`
- [ ] `test_token_expired_returns_401_AUTH_TOKEN_EXPIRED`: 過期 Bearer Token 回傳 401 + `AUTH_TOKEN_EXPIRED`

### 27. A/B Testing 框架

- [ ] `test_ab_test_deterministic_user_assignment`: 同一 `user_id` + `experiment_id` 每次 `get_variant()` 回傳相同 variant
- [ ] `test_ab_test_uses_sha256_not_python_hash`: 使用 `hashlib.sha256` 而非 Python 內建 `hash()`
- [ ] `test_ab_test_respects_traffic_split_percentages`: traffic_split 50/50 時，variant_hash < 50 進 control，>= 50 進 treatment
- [ ] `test_ab_test_returns_control_as_fallback`: variant_hash 超出所有 cumulative 時回傳 control
- [ ] `test_ab_test_run_experiment_uses_correct_variant_prompt`: `run_experiment()` 使用指定 variant 的 prompt
- [ ] `test_ab_test_analyze_results_returns_metric_data`: `analyze_results()` 回傳 variant + metric_name + metric_value + sample_size
- [ ] `test_ab_test_auto_promote_minimum_sample_check`: 任何 variant sample_size < 100 時不回腳
- [ ] `test_ab_test_auto_promote_threshold_check`: 最佳 variant 領先幅度 < 0.05 時不回腳
- [ ] `test_ab_test_auto_promote_updates_experiment_status`: 符合條件時將 experiment status 改為 `completed`
- [ ] `test_ab_test_auto_promote_returns_winning_variant`: 成功時回傳 winning variant name

### 28. OpenTelemetry Tracing

- [ ] `test_tracer_sets_platform_attribute`: `handle_message` span 包含 `platform` attribute
- [ ] `test_tracer_sets_user_id_attribute`: span 包含 `user_id` attribute
- [ ] `test_tracer_creates_nested_span_for_emotion_analysis`: `emotion_analysis` 為 `handle_message` 的子 span
- [ ] `test_tracer_creates_nested_span_for_knowledge_query`: `knowledge_query` 為子 span
- [ ] `test_tracer_sets_knowledge_source_and_confidence_attributes`: knowledge span 包含 `knowledge_source` 和 `confidence`

### 29. Prometheus Metrics

- [ ] `test_metric_response_duration_histogram_labels`: histogram 有 `platform`, `knowledge_source` labels
- [ ] `test_metric_requests_total_counter_labels`: counter 有 `platform`, `status` labels
- [ ] `test_metric_fcr_total_labels`: counter 有 `resolved` (true/false) label
- [ ] `test_metric_knowledge_hit_total_labels`: counter 有 `layer` (rule/rag/wiki/escalate) label
- [ ] `test_metric_pii_masked_total_labels`: counter 有 `pii_type` label
- [ ] `test_metric_escalation_queue_size_gauge`: 為 gauge 而非 counter
- [ ] `test_metric_emotion_escalation_total`: emotion 觸發 counter
- [ ] `test_metric_llm_tokens_total_labels`: counter 有 `model`, `direction` (input/output) labels

### 30. 告警規則

- [ ] `test_alert_high_latency_triggers_at_p95_1s`: `HighLatency` alert 表達式 `> 1.0` for `5m`
- [ ] `test_alert_high_error_rate_triggers_at_5_percent`: `HighErrorRate` alert `> 0.05` for `3m`
- [ ] `test_alert_escalation_queue_backlog_triggers_at_50`: `EscalationQueueBacklog` alert `> 50` for `10m`
- [ ] `test_alert_sla_breach_triggers_at_5_per_hour`: `SLABreach` alert `> 5` in `1h`

### 31. Redis Streams 異步處理（完整）

- [ ] `test_async_message_processor_classmethod_factory_creates_instance`: `create()` 可用 classmethod 建立 instance（避免 `__init__` 中 await）
- [ ] `test_async_message_processor_consume_with_block`: `block=5000` 時最多等 5 秒
- [ ] `test_async_message_processor_xreadgroup_reads_from_stream`: 正確使用 `xreadgroup` 而非 `xread`

### 32. 指數退避重試（完整）

- [ ] `test_retry_respects_max_delay`: delay 上限為 `max_delay`
- [ ] `test_retry_jitter_half_to_full_range`: jitter enabled 時 delay 在 `[0.5*delay, 1.0*delay]` 範圍內隨機

### 33. TDE 加密 + Redis 安全

- [ ] `test_redis_tls_enabled`: Redis 連線使用 TLS port 6380
- [ ] `test_redis_requirepass_auth`: Redis 需要密碼認證（`requirepass`）
- [ ] `test_redis_default_user_disabled`: `default_user_disabled=true`
- [ ] `test_redis_acl_enabled`: ACL enabled
- [ ] `test_postgresql_tde_enabled`: PostgreSQL TDE 啟用，algorithm = AES-256
- [ ] `test_ssl_mode_verify_full`: PostgreSQL SSL mode = verify-full
- [ ] `test_encryption_config_table_schema`: `encryption_config` 表包含 `component`, `algorithm`, `tde_enabled`, `last_key_rotation`, `next_key_rotation`, `status`

### 34. Schema 遷移管理

- [ ] `test_alembic_migration_001_upgrade_creates_phase1_tables`: upgrade() 建立 Phase 1 的 8 張表
- [ ] `test_alembic_migration_001_downgrade_reverses`: downgrade() 可完全反轉 upgrade()
- [ ] `test_alembic_migration_002_upgrade_adds_phase2_tables`: phase2 upgrade 建立 emotion_history + edge_cases
- [ ] `test_alembic_migration_003_upgrade_adds_phase3_tables`: phase3 upgrade 建立 RBAC 相關 + experiments 等 7 張表
- [ ] `test_schema_migrations_version_uniqueness`: `schema_migrations.version` 為 PRIMARY KEY，不可重複

### 35. 備份與 Rollback

- [ ] `test_knowledge_soft_delete_for_rollback`: 知識庫更新使用 `version + is_active` 軟刪除
- [ ] `test_experiment_abort_sets_status_aborted`: `experiment_abort` 將 status 設為 `aborted`
- [ ] `test_experiment_abort_returns_control_traffic`: abort 後所有流量回到 control variant

### 36. 降級策略

- [ ] `test_degradation_level_1_rag_only`: LLM p95 > 3s 時降至 Layer 1+2（關閉 Layer 3）
- [ ] `test_degradation_level_2_rule_only`: LLM 連續失敗 > 3 次時僅用 Layer 1
- [ ] `test_degradation_level_3_readonly_cache`: DB p95 > 2s 時啟用 Redis 唯讀快取
- [ ] `test_degradation_level_4_maintenance_message`: 全量服務中斷時回傳靜態維護訊息

### 37. 負載測試（k6 場景對應驗證）

- [ ] `test_load_smoke_10_vus_1m_passes`: smoke test 10 VUs 1 分鐘成功
- [ ] `test_load_normal_200_vus_p95_under_1s`: load test 200 VUs 10 分鐘 p95 < 1s
- [ ] `test_load_stress_2000_tps`: stress test 可達 2000 TPS
- [ ] `test_load_spike_3000_vus_recovers`: spike test 3000 VUs 結束後系統恢復正常

### 38. i18n 擴充

- [ ] `test_current_scope_zh_tw_pii_patterns`: Phase 1-3 PII patterns 僅針對台灣格式
- [ ] `test_expansion_roadmap_defined`: i18n 擴充 roadmap 文件存在於 `i18n/` 目錄（zh-CN、en、ja 三個 locale）
- [ ] `test_expansion_roadmap_zh_cn_content_exists_and_non_empty`: `i18n/zh-CN/` 目錄下存在非空白內容（驗證檔案存在且非 placeholder）
- [ ] `test_expansion_roadmap_en_content_exists_and_non_empty`: `i18n/en/` 目錄下存在非空白內容
- [ ] `test_expansion_roadmap_ja_content_exists_and_non_empty`: `i18n/ja/` 目錄下存在非空白內容

### 39. 成本模型

- [ ] `test_cost_estimation_layer1_zero`: Layer 1 規則匹配 cost = $0
- [ ] `test_cost_estimation_layer2_per_query`: Layer 2 RAG 約 $0.003/次
- [ ] `test_cost_estimation_layer3_per_query`: Layer 3 LLM 生成約 $0.009/次
- [ ] `test_monthly_cost_under_500_at_100k_conversations`: 10 萬對話月成本 < $500

### 40. ODD SQL 查詢驗證（13 條）

#### Phase 1
- [ ] `test_odd_fcr_rate_query_rounds_to_2_decimals`: FCR 查詢 ROUND 到小數點後 2 位
- [ ] `test_odd_latency_p95_query_grouped_by_platform`: 延遲查詢以 platform 分組
- [ ] `test_odd_knowledge_hit_query_aggregates_by_source`: 知識命中查詢 GROUP BY knowledge_source

#### Phase 2
- [ ] `test_odd_csat_query_calculates_avg_and_p95`: CSAT 查詢包含 AVG + PERCENTILE_CONT(0.95)
- [ ] `test_odd_knowledge_hit_distribution_includes_percentage`: 命中分布查詢包含百分比計算
- [ ] `test_odd_feedback_query_joins_messages`: 回饋分析需 JOIN messages table
- [ ] `test_odd_sla_compliance_query_calculates_by_priority`: SLA 遵守率依 priority 分組
- [ ] `test_odd_emotion_stats_query_groups_by_date_and_category`: 情緒統計依日期 + category 分組
- [ ] `test_odd_security_block_rate_query_calculates_percentage`: 安全阻擋率 = blocked/total * 100

#### Phase 3
- [ ] `test_odd_cost_per_resolution_query_divides_total_cost_by_resolved`: 成本效益分析 = SUM(cost) / COUNT(resolved)
- [ ] `test_odd_monthly_cost_query_estimates_by_layer`: 月度成本依 knowledge_source 估算
- [ ] `test_odd_pii_audit_query_sums_by_date`: PII 稽核摘要 SUM(mask_count) GROUP BY DATE
- [ ] `test_odd_rbac_audit_query_joins_users_and_roles`: RBAC 審計需 JOIN users + roles + role_assignments
- [ ] `test_odd_ab_experiment_results_query_shows_running_only`: A/B 實驗查詢過濾 status='running'

---

## 41. 商業 KPI 驗證（對應 VERIFICATION_PLAN 章節 2.1 / 3.1 / 4.1）

### Phase 1 商業目標

- [ ] `test_kpi_fcr_phase1_target_50_percent`: ODD SQL 查詢 FCR >= 50%（Layer 1 命中且未轉接 / 總 in_scope 對話）
- [ ] `test_kpi_csat_phase1_baseline_improvement_15_percent`: satisfaction_score 相比無機器人基線提升 +15%
- [ ] `test_kpi_p95_latency_phase1_under_3s`: k6 smoke test，`omnibot_response_duration_seconds` p95 < 3000ms
- [ ] `test_kpi_platform_support_telegram_and_line`: 兩平台各自送測試訊息並確認回覆

### Phase 2 商業目標

- [ ] `test_kpi_fcr_phase2_target_80_percent`: ODD SQL（含 Layer 1+2+3+4 貢獻）FCR >= 80%
- [ ] `test_kpi_csat_phase2_improvement_35_percent`: satisfaction_score 相比 Phase 1 基線提升 +20%（累計 +35%）
- [ ] `test_kpi_p95_latency_phase2_under_1.5s`: k6 load test p95 < 1500ms
- [ ] `test_kpi_platform_support_4_platforms`: Telegram + LINE + Messenger + WhatsApp 全部可正常收發
- [ ] `test_kpi_security_block_rate_above_95_percent`: 安全阻擋計數 / 總請求 >= 95%

### Phase 3 商業目標

- [ ] `test_kpi_fcr_phase3_target_90_percent`: ODD SQL FCR >= 90%（Phase 2 基礎 + A/B 優化）
- [ ] `test_kpi_availability_99.9_percent_monthly`: Prometheus 監控月可用性 >= 99.9%
- [ ] `test_kpi_p95_latency_phase3_under_1s`: k6 stress test p95 < 1000ms
- [ ] `test_kpi_disaster_recovery_under_5_minutes`: 演練測試，模擬全量故障後 5 分鐘內恢復
- [ ] `test_kpi_monthly_cost_under_500_usd`: 成本儀表板顯示月成本 < $500（10 萬對話規模）

---

## 42. API 端點對應測試（對應 VERIFICATION_PLAN 章節 2.3）

### Webhook 端點

- [ ] `test_webhook_telegram_valid_signature_returns_200`: POST `/api/v1/webhook/telegram` 正確簽名回傳 200
- [ ] `test_webhook_telegram_invalid_signature_returns_401`: 錯誤簽名回傳 401 + `AUTH_INVALID_SIGNATURE`
- [ ] `test_webhook_telegram_rate_limited_returns_429`: Rate Limit 超出回傳 429 + `RATE_LIMIT_EXCEEDED`
- [ ] `test_webhook_line_valid_signature_returns_200`: POST `/api/v1/webhook/line` 正確簽名回傳 200
- [ ] `test_webhook_line_invalid_signature_returns_401`: 錯誤簽名回傳 401 + `AUTH_INVALID_SIGNATURE`
- [ ] `test_webhook_line_rate_limited_returns_429`: Rate Limit 超出回傳 429 + `RATE_LIMIT_EXCEEDED`

### 知識庫 CRUD

- [ ] `test_api_knowledge_get_pagination_page_0_edge_case`: `page=0` 時觸發 VALIDATION_ERROR 422
- [ ] `test_api_knowledge_get_limit_101_clamped_to_100`: `limit=101` 時自動限制為 100
- [ ] `test_api_knowledge_post_idempotent`: 重複 POST 同一知識條目不回傳錯誤（idempotent）
- [ ] `test_api_knowledge_get_category_filter`: `category` query param 正確過濾結果
- [ ] `test_api_knowledge_bulk_import_100_records`: 單次批次匯入 100 筆成功

### 對話記錄

- [ ] `test_api_conversations_list_pagination`: 分頁參數正常運作
- [ ] `test_api_conversations_list_filter_by_platform`: 可依 platform 篩選
- [ ] `test_api_conversations_list_filter_by_timerange`: 可依時間範圍篩選

### 健康檢查

- [ ] `test_api_health_returns_200_with_all_fields`: 包含 status, postgres, redis, uptime_seconds
- [ ] `test_api_health_postgres_down_returns_degraded`: PostgreSQL 連線失敗時 status = "degraded"
- [ ] `test_api_health_redis_down_returns_degraded`: Redis 連線失敗時 status = "degraded"

---

## 43. 跨 Phase 一致性驗證（對應 VERIFICATION_PLAN 章節 5）

### 版本一致性

- [ ] `test_version_consistency_error_codes_count_p1`: Phase 1 環境有且只有 5 個錯誤碼（AUTH_INVALID_SIGNATURE / RATE_LIMIT_EXCEEDED / KNOWLEDGE_NOT_FOUND / VALIDATION_ERROR / INTERNAL_ERROR）
- [ ] `test_version_consistency_error_codes_count_p2`: Phase 2 新增 LLM_TIMEOUT，共 6 個
- [ ] `test_version_consistency_error_codes_count_p3`: Phase 3 新增 AUTH_TOKEN_EXPIRED / AUTHZ_INSUFFICIENT_ROLE，共 8 個
- [ ] `test_version_consistency_schema_tables_p1`: Phase 1 完成後共 8 張核心表
- [ ] `test_version_consistency_schema_tables_p2`: Phase 2 完成後累計 10 張表
- [ ] `test_version_consistency_schema_tables_p3`: Phase 3 完成後累計 18 張表
- [ ] `test_version_consistency_odd_sql_total_13_queries`: 全部 13 支 ODD SQL 皆可正常執行

### API 向後相容

- [ ] `test_backward_compat_phase1_tests_pass_in_phase2_env`: Phase 1 所有測試在 Phase 2 環境仍通過（Phase 2 不破壞 Phase 1 API）
- [ ] `test_backward_compat_phase1p2_tests_pass_in_phase3_env`: Phase 1+2 所有測試在 Phase 3 環境仍通過
- [ ] `test_backward_compat_new_fields_optional`: Phase 2/3 新增欄位皆為 Optional，不影響舊客戶端解析

### 資料模型一致性

- [ ] `test_consistency_knowledge_result_id_minus_one_means_escalate`: 三 Phase 一致，`id=-1` 代表轉接
- [ ] `test_consistency_confidence_range_0_to_1`: confidence 分數範圍始終為 0.0-1.0
- [ ] `test_consistency_platform_enum_telegram_line_phase1`: Phase 1 Platform 僅有 TELEGRAM + LINE
- [ ] `test_consistency_platform_enum_4_platforms_phase2`: Phase 2 起 Platform 包含 MESSENGER + WHATSAPP
- [ ] `test_consistency_emotion_category_three_values`: EmotionCategory 僅接受 POSITIVE / NEUTRAL / NEGATIVE
- [ ] `test_consistency_conversation_state_7_states`: ConversationState 共 7 個狀態，狀態機轉移圖封閉
- [ ] `test_consistency_fcr_layer_weights_phase2_total_100_percent`: Layer 1 (40%) + Layer 2 (40%) + Layer 3 (10%) + Layer 4 (10%) = 100%

### 安全層職責一致

- [ ] `test_consistency_l2_does_not_do_pattern_matching`: InputSanitizer 只做 NFKC + 控制字元移除，不做正規表示式偵測（L3 負責 injection，L4 負責 PII）

---

## 44. 缺口追蹤 G-01 ~ G-09（對應 VERIFICATION_PLAN 章節 6.1）

> 以下為 VERIFICATION_PLAN 發現的 9 個規格缺口，補入測試以確保實作時被發現。
> **資訊已完整內嵌，無需另行查閱 VERIFICATION_PLAN.md。**

---

### G-01 空字串處理｜優先：中｜處置：明定回傳 `""`

**缺口描述**：`InputSanitizer.sanitize()` 未定義對空字串的處理（回傳 `""` 或 `None`？）

### G-02 keywords 欄位型別｜優先：中｜處置：明定 `TEXT[]` PostgreSQL 原生陣列

**缺口描述**：`RuleMatch` 的 `keywords` 欄位型別未說明（PostgreSQL array 還是 JSON array？）

### G-03 LLM Layer 3 Prompt Template｜優先：低｜處置：附基準 prompt 以便可重現測試

**缺口描述**：Phase 2 LLM Layer 3 的 prompt template 未提供，僅預留 interface

### G-04 assign 已 resolved 的 escalation 行為｜優先：中｜處置：明定回傳 0 row affected 或拋例外

**缺口描述**：`EscalationManager.assign()` 當 escalation 已 resolved 時行為未定義

### G-05 Redis Streams 訊息格式｜優先：中｜處置：規格提供訊息結構範例

**缺口描述**：Phase 3 Redis Streams 的訊息格式（message schema）未定義

### G-06 ABTestManager traffic_split JSONB 型別｜優先：低｜處置：明定結構如 `{"control": 50, "treatment": 50}`

**缺口描述**：`ABTestManager.get_variant()` 的 `experiment["traffic_split"]` 型別未說明（JSONB）

### G-07 降級策略 Level 1-4 具體實作｜優先：高｜處置：需補充 MetricsAlert / HealthCheck 具體實作

**缺口描述**：降級策略 Level 1-4 的觸發條件在程式碼中未見實作，規格僅描述性說明

### G-08 pii_audit_log action 欄位枚舉值｜優先：低｜處置：明定允許值

**缺口描述**：`pii_audit_log` 的 `action` 欄位枚舉值（mask/unmask/restore）未定義

### G-09 Rate Limiter Redis fallback 行為｜優先：高｜處置：明定 block all（安全預設）

**缺口描述**：Phase 1 Rate Limiter 未說明當 Redis 不可用時的 fallback 行為

---

以下為對應測試案例：

### G-01 空字串處理（中等優先）

- [ ] `test_sanitizer_empty_string_returns_empty_string`: `sanitize("")` 回傳 `""` 而非 `None`
- [ ] `test_sanitizer_whitespace_only_returns_empty_string`: `sanitize("   ")` 回傳 `""`

### G-02 keywords 欄位型別（中等優先）

- [ ] `test_knowledge_base_keywords_is_postgresql_array`: `keywords` 欄位為 PostgreSQL `TEXT[]` 原生陣列（非 JSON）
- [ ] `test_knowledge_query_keywords_matching_uses_any`: SQL 中使用 `%s = ANY(keywords)` 而非 JSON 查詢

### G-03 LLM Layer 3 Prompt Template（低優先）

- [ ] `test_llm_layer3_base_prompt_is_reproducible`: 基准 prompt template 存在於設定檔，可抽換

### G-04 assign 已 resolved 的 escalation 行為（中等優先）

- [ ] `test_escalation_assign_on_resolved_returns_zero_affected`: 對已 resolved 的 escalation 執行 `assign()` 不拋例外，回傳 0 row affected
- [ ] `test_escalation_assign_on_resolved_does_not_update_picked_at`: 已 resolved 的記錄 `picked_at` 不被更新

### G-05 Redis Streams 訊息格式（中等優先）

- [ ] `test_redis_streams_message_schema_defined`: 訊息格式（message schema）已定義於程式碼或文件中
- [ ] `test_redis_streams_consumer_handles_unknown_fields_gracefully`: 消費者對未知欄位可容忍（forward compatibility）

### G-06 ABTestManager traffic_split JSONB 型別（低優先）

- [ ] `test_ab_traffic_split_is_valid_jsonb_structure`: `traffic_split` 為 `{"control": 50, "treatment": 50}` 格式
- [ ] `test_ab_traffic_split_sums_to_100`: traffic_split 所有 percentage 相加等於 100

### G-07 降級策略 Level 1-4 具體實作（高優先）

- [ ] `test_degradation_l1_triggers_on_llm_p95_above_3s`: LLM p95 > 3s 時自動啟用 Level 1（Layer 1+2 only，快取啟用）
- [ ] `test_degradation_l1_caches_responses_for_5_minutes`: Level 1 啟用時相同問題 5 分鐘內回傳快取
- [ ] `test_degradation_l2_triggers_on_llm_consecutive_failures_3`: LLM 連續失敗 > 3 次時自動啟用 Level 2（Layer 1 only）
- [ ] `test_degradation_l2_unmatched_automatically_escalates`: Level 2 下無匹配直接轉接人工
- [ ] `test_degradation_l3_triggers_on_db_p95_above_2s`: DB p95 > 2s 時啟用 Level 3（Redis 唯讀快取）
- [ ] `test_degradation_l3_pauses_noncritical_writes`: Level 3 下暫停回饋收集、稽核日誌寫入，恢復後批次寫入
- [ ] `test_degradation_l4_triggers_on_full_outage`: 核心服務全部不可用時回傳靜態維護訊息
- [ ] `test_degradation_l4_logs_requests_to_local_file`: Level 4 下所有請求記錄至本地檔案，恢復後可重播

### G-08 pii_audit_log action 欄位枚舉值（低優先）

- [ ] `test_pii_audit_action_enum_mask_unmask_restore`: `action` 欄位僅接受 `mask` / `unmask` / `restore`（或明確定義的其他枚舉值）

### G-09 Rate Limiter Redis fallback 行為（高優先）

- [ ] `test_rate_limiter_redis_unavailable_blocks_all_by_default`: Redis 不可用時，Rate Limiter 預設 block all（安全優先）
- [ ] `test_rate_limiter_fallback_allow_all_if_configured`: 若有 `RATE_LIMIT_FALLBACK=allow_all` 配置，Redis 掛掉時允許通過
- [ ] `test_rate_limiter_fallback_logs_warning_when_redis_down`: Redis fallback 觸發時 StructuredLogger 寫入 WARN 層級日誌

---

## 45. TDD 執行順序（對應 VERIFICATION_PLAN 章節 7）

> 測試應依此順序分輪執行，確保依賴關係正確

### 第 1 輪：Phase 1 單元測試

- [ ] Phase 1 模組全部通過（InputSanitizer, PIIMasking, RateLimiter, WebhookVerifier, KnowledgeLayerV1, BasicEscalationManager, StructuredLogger）
- [ ] 全部 RED → GREEN → REFACTOR 循環已完成

### 第 2 輪：Phase 1 整合測試 + API 測試

- [ ] Webhook 接收 → Sanitizer → PII → Knowledge → Response 完整流程
- [ ] ODD SQL FCR 查詢驗證 Phase 1 目標 >= 50%
- [ ] API 端點（webhook / knowledge / conversations / health）全部 200/401/429/404/422 正確

### 第 3 輪：Phase 2 單元測試

- [ ] DST, EmotionTracker, HybridKnowledgeV7, PromptInjectionDefense, GroundingChecker, PIIMaskingV2, EscalationManager
- [ ] 新 Webhook verifier（Messenger, WhatsApp）
- [ ] Redis Streams AsyncMessageProcessor, RetryStrategy

### 第 4 輪：Phase 2 整合測試

- [ ] 4-Layer Hybrid Query 完整流程（Layer 1 → RRF → Layer 3 → Layer 4）
- [ ] DST 狀態轉移整合（多輪對話）
- [ ] 黃金數據集 500 筆回歸測試（edge_cases 表）
- [ ] ODD SQL 安全阻擋率驗證 >= 95%

### 第 5 輪：Phase 3 單元測試

- [ ] RBACEnforcer（4 角色 × 5 資源 × 行為矩陣）
- [ ] ABTestManager（確定性分配 + auto_promote）
- [ ] AsyncMessageProcessor, RetryStrategy, TDERedisConfig

### 第 6 輪：Phase 3 E2E + 負載測試

- [ ] k6 smoke test（10 VUs, 1m, p95 < 3000ms）
- [ ] k6 load test（200 VUs, 10m, p95 < 1000ms, error rate < 1%）
- [ ] k6 stress test（500→2000→3000 VUs）
- [ ] k6 spike test（突發 3000 VUs）
- [ ] Kubernetes 部署驗證（3 replicas, maxUnavailable=1, maxSurge=1）

### 第 7 輪：最終一致性驗證

- [ ] 全部 13 支 ODD SQL 執行成功
- [ ] FCR >= 90%, 可用性 >= 99.9%, p95 < 1.0s
- [ ] 跨 Phase 向後相容測試通過（Phase 1+2 測試在 Phase 3 環境仍通過）
- [ ] G-01~G-09 缺口測試全部通過

---

## 46. 測試環境矩陣（對應 VERIFICATION_PLAN 章節 8）

### 各環境驗證

- [ ] `test_env_unit_all_modules_use_mocks`: unit 環境所有外部依賴（DB、Redis、LLM）使用 mock
- [ ] `test_env_integration_uses_test_db_with_seed`: integration 環境使用測試資料庫（含 seed data）
- [ ] `test_env_integration_llm_can_use_mock_or_cheap`: integration 可用 mock LLM 或最便宜模型
- [ ] `test_env_staging_uses_same_llm_as_prod`: staging LLM 模型與 production 相同
- [ ] `test_env_staging_data_is_anonymized_prod_subset`: staging 資料為匿名化的 production 子集
- [ ] `test_env_production_real_model_and_data`: production 使用正式模型與真實資料

---

## 47. Release Gate（對應 VERIFICATION_PLAN 章節 9）

> 每個 Phase 必須同時滿足以下所有條件才可釋出

### Phase 1 Release Gate

- [ ] `test_gate_p1_fcr_at_least_50_percent`: FCR >= 50%
- [ ] `test_gate_p1_p95_latency_under_3s`: p95 < 3.0s
- [ ] `test_gate_p1_all_8_schema_tables_exist`: users, conversations, messages, knowledge_base, platform_configs, escalation_queue, user_feedback, security_logs 全部存在
- [ ] `test_gate_p1_all_3_odd_sql_executable`: 3 支 ODD SQL 查詢皆可正常執行

### Phase 2 Release Gate

- [ ] `test_gate_p2_fcr_at_least_80_percent`: FCR >= 80%
- [ ] `test_gate_p2_p95_latency_under_1.5s`: p95 < 1.5s
- [ ] `test_gate_p2_golden_dataset_at_least_500_records`: edge_cases 表 >= 500 筆
- [ ] `test_gate_p2_security_block_rate_measurable`: 安全阻擋率可被測量（LLM_TIMEOUT 錯誤碼存在）

### Phase 3 Release Gate

- [ ] `test_gate_p3_fcr_at_least_90_percent`: FCR >= 90%
- [ ] `test_gate_p3_p95_latency_under_1s`: p95 < 1.0s
- [ ] `test_gate_p3_availability_99.9_percent`: Prometheus 可用性 >= 99.9%
- [ ] `test_gate_p3_all_4_rbac_roles_tested`: admin / editor / agent / auditor 四角色皆已測試
- [ ] `test_gate_p3_ab_autopromote_logic_verified`: A/B auto_promote 閾值 + 最小樣本邏輯驗證

---

## 48. 安全性測試 / 紅隊（對應 VERIFICATION_PLAN 章節 2/3/4 安全性測試）

### Prompt Injection 紅隊

- [ ] `test_redteam_prompt_injection_direct_webhook_payload`: 直接 POST injection payload 到 `/api/v1/webhook/telegram` 並確認被 L3 阻擋
- [ ] `test_redteam_prompt_injection_mixed_with_normal_text`: 正常句子夾雜 injection 指令仍被偵測
- [ ] `test_redteam_prompt_injection_unicode_obfuscation`: 使用 Unicode 混淆的 injection 仍被偵測
- [ ] `test_redteam_prompt_injection_sandwich_attack`: Sandwich attack（正常 system + injection + normal）被正確處理

### RBAC 紅隊

- [ ] `test_redteam_rbac_agent_cannot_delete_knowledge`: agent 角色直接呼叫 DELETE API 被 403 阻擋
- [ ] `test_redteam_rbac_editor_cannot_access_audit`: editor 角色讀取 audit 資源被 403 阻擋
- [ ] `test_redteam_rbac_auditor_cannot_write`: auditor 角色執行寫入被 403 阻擋
- [ ] `test_redteam_rbac_token_tampering`: 篡改 Bearer Token 企圖提權被 401 阻擋

### PII 紅隊

- [ ] `test_redteam_pii_mixed_real_fake_card_luhn`: 混合真實有效卡號與無效卡號，僅有效者被遮蔽
- [ ] `test_redteam_pii_international_phone_masks_taiwan_only`: 台灣以外格式的電話（e.g. +1-xxx）不應被誤判為 PII

### Rate Limiting 紅隊

- [ ] `test_redteam_rate_limit_burst_attack_blocked`: 瞬間發送 capacity+1 請求，第 (capacity+1) 個被 429 阻擋
- [ ] `test_redteam_rate_limitDistributed_from_multiple_user_ids`: 攻擊者使用多個 user_id 分散请求，仍被每-user rate limit 阻擋

---

## 49. 黃金數據集與資料品質（對應 VERIFICATION_PLAN 章節 3.5 Edge Cases）

### 黃金數據集

- [ ] `test_golden_dataset_count_at_least_500_by_phase2_end`: Phase 2 結束時 edge_cases 表 >= 500 筆
- [ ] `test_golden_dataset_6_types_covered`: 黃金數據集涵蓋 6 種類型（語音亂碼 / 拼寫錯誤 / 方言簡稱 / 多意圖 / 情感爆發 / Prompt Injection）
- [ ] `test_golden_dataset_used_in_regression`: edge_cases.used_in_regression = TRUE 的項目用於自動化回歸測試
- [ ] `test_golden_dataset_status_approved_or_rejected`: 所有 edge_cases 有明確 status（pending/approved/rejected），不接受 NULL

### Edge Case 各類型驗證

- [ ] `test_edge_asr_transcription_noise`: 「我想查詢~訂單」此類語音轉文字乱码可被正常處理
- [ ] `test_edge_spelling_error_tolerance`: 「運費」錯誤拼寫為「雲費」仍能被規則匹配
- [ ] `test_edge_abbreviation_sop_context_aware`: 「SOP」在正確上下文被理解
- [ ] `test_edge_multi_intent_single_message`: 「查訂單順便問退貨」此類多意圖單一訊息不崩潰
- [ ] `test_edge_emotion_burst_sequence`: 連續 3 次負面情緒輸入觸發 should_escalate()
- [ ] `test_edge_prompt_injection_high_priority`: Prompt Injection 被 L3 阻擋，不進入 LLM

---

## 50. Phase 3 部署與災備驗證（對應 VERIFICATION_PLAN 章節 4.5）

### Docker Compose

- [ ] `test_deploy_docker_compose_all_services_healthy`: `docker-compose up` 後所有 service health check 通過
- [ ] `test_deploy_health_endpoint_returns_200_after_startup`: 服務啟動完成後 `/api/v1/health` 回傳 200

### Kubernetes

- [ ] `test_deploy_k8s_replicas_count_3`: `kubectl get deployment` 顯示 replicas == 3
- [ ] `test_deploy_k8s_rolling_update_max_unavailable_1`: Rolling update maxUnavailable = 1
- [ ] `test_deploy_k8s_rolling_update_max_surge_1`: Rolling update maxSurge = 1
- [ ] `test_deploy_k8s_rolling_update_completes_without_downtime`: 滾動更新期間服務不中斷

### 備份與還原

- [ ] `test_backup_pg_basebackup_and_restore`: `pg_basebackup` 備份後可完整 restore，資料不丟失
- [ ] `test_backup_redis_rdb_and_aof_restore`: Redis RDB + AOF 備份可還原
- [ ] `test_backup_knowledge_soft_delete_rollback`: 知識庫軟刪除後可 rollback（old version is_active=TRUE）

### Rollback 演練

- [ ] `test_rollback_experiment_abort_sets_status_aborted`: 緊急中止 A/B 實驗後 status = 'aborted'
- [ ] `test_rollback_experiment_returns_all_traffic_to_control`: abort 後所有流量回到 control variant

---

## 貫穿三階段的 Cross-Cutting 驗證

### API Error Codes（8 個錯誤碼）

- [ ] `test_error_AUTH_INVALID_SIGNATURE_401`: 簽名驗證失敗回傳 401 + `AUTH_INVALID_SIGNATURE`
- [ ] `test_error_RATE_LIMIT_EXCEEDED_429`: Rate Limit 超過回傳 429 + `RATE_LIMIT_EXCEEDED`
- [ ] `test_error_KNOWLEDGE_NOT_FOUND_404`: 知識條目不存在回傳 404 + `KNOWLEDGE_NOT_FOUND`
- [ ] `test_error_VALIDATION_ERROR_422`: 參數驗證失敗回傳 422 + `VALIDATION_ERROR`
- [ ] `test_error_INTERNAL_ERROR_500`: 內部錯誤回傳 500 + `INTERNAL_ERROR`
- [ ] `test_error_LLM_TIMEOUT_504`: LLM API 逾時回傳 504 + `LLM_TIMEOUT`（Phase 2）
- [ ] `test_error_AUTH_TOKEN_EXPIRED_401`: Bearer Token 過期回傳 401 + `AUTH_TOKEN_EXPIRED`（Phase 3）
- [ ] `test_error_AUTHZ_INSUFFICIENT_ROLE_403`: 權限不足回傳 403 + `AUTHZ_INSUFFICIENT_ROLE`（Phase 3）

### 資料完整性

- [ ] `test_knowledge_base_embeddings_dimension_384`: 向量維度嚴格等於 384
- [ ] `test_all_platform_enum_values_valid`: Platform 僅接受 TELEGRAM/LINE/MESSENGER/WHATSAPP（Phase 2 後）
- [ ] `test_all_message_type_enum_values_valid`: MessageType 僅接受 TEXT/IMAGE/STICKER/LOCATION/FILE
- [ ] `test_conversation_status_default_active`: 新對話預設 `status='active'`
- [ ] `test_emotion_intensity_range_0_to_1`: `intensity` 欄位 CHECK `>= 0 AND <= 1`

---

## 驗證完成標準

**開始実装前請確認：**

- [ ] 每個 test case 名稱清晰描述預期行為
- [ ] 每個 test case 在 RED 階段會失敗（因為功能尚不存在）
- [ ] 每個 test case 有對應的 assert 陳述式
- [ ] 所有測試採用真實程式碼（mock 僅在不可避免時使用）
- [ ] Edge cases 和錯誤情境皆有覆蓋

**TDD 循環遵守聲明：**

```
"NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST"
```

若有任何條目未滿足，請砍掉重來。

---

*清單版本: v1.1*
*依據規格: OmniBot Phase 1-3 (v7.0, 2026-04-15)*
*總 test cases: 約 210 條 + 缺口補充條目*
*與 VERIFICATION_PLAN.md v1.0 對比後補充以下章節 41-48*
