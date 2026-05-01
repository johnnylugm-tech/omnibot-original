# OmniBot Phase Voice: IVR 電話語音入口 — 規格文件

---

## 專案概述

| 項目 | 內容 |
|------|------|
| **專案名稱** | OmniBot - 多平台客服機器人 |
| **階段** | Phase Voice（IVR 電話語音入口） |
| **目標** | 支援電話語音互動（撥入 → IVR 導航 → 語音客服機器人） |
| **核心原則** | 復用既有處理管線、新增語音轉換層（ASR/TTS/IVR/DTMF） |
| **開發時間** | 4-6 週 |
| **前置條件** | Phase 1 + Phase 2 + Phase 3 完成（Phase Web 可選） |

### 與既有 Phase 的關係

Phase Voice **依賴** Phase 1 + Phase 2 的核心處理管線：
- UnifiedMessage / UnifiedResponse 格式
- HybridKnowledgeLayer（Layer 1-4）
- InputSanitizer、PII Masking、Emotion Analyzer、DST
- conversations / messages 資料庫 Schema
- Escalation Manager（Layer 4 轉接）

Phase Voice **不依賴** Phase Web，但 Phase Web 的 JWT 認證框架和 WebSocket 架構經驗可作為參考。

---

## 商業目標

| KPI | Phase Voice 目標 | 實現路徑 |
|-----|-----------------|----------|
| **語音 FCR** | >= 70% | IVR 意圖識別 + Layer 1-4 文字處理管線 |
| **IVR 完成率** | >= 80% | 成功走到終點不轉人工的比例 |
| **平均通話時長** | < 4 分鐘 | IVR 效率 + 快速意圖識別 |
| **ASR 錯誤率（WER）** | < 10% | Whisper 模型品質 + 噪音處理 |
| **來話接通率** | >= 98% | Twilio 基礎建設 + HA 部署 |
| **通訊成本** | < $0.05/分鐘 | Twilio 計費模型 |

---

## 系統架構 Phase Voice

### 完整架構圖

```
+---------------------------------------------------------------------+
|                    OmniBot Phase Voice 完整架構                        |
+---------------------------------------------------------------------+

  +------------------+  +------------------+  +------------------+
  |   PSTN 電話網    |  |  VoIP / SIP     |  |   網頁電話       |
  |   (一般市話)    |  |  (Twilio/Vonage)|  |   (WebRTC)      |
  +--------+---------+  +--------+---------+  +--------+---------+
           │                      │                      │
           └──────────────────────┼──────────────────────┘
                                  │
           +----------------------+----------------------+
           |         Telecom Adapter Layer               |
           |  (Twilio/Vonage Client — 來話被動接收模式)   |
           +----------------------+----------------------+
                                  │
           +----------------------+----------------------+
           |         VoicePlatformAdapter              |
           |  ANI 身份識別 / Call Events / DTMF 處理    |
           +----------------------+----------------------+
                                  │
  +---------------------------------------------------------------+
  |              IVR Flow Engine ← Phase Voice NEW                  |
  |         PROMPT / MENU / COLLECT / TRANSFER / CONDITION / END  |
  +---------------------------------------------------------------+
                                  │
  +---------------------------------------------------------------+
  |              ASR Adapter ← Phase Voice NEW                       |
  |         Whisper 本地部署 / Google STT / Azure Speech           |
  |         語音 → 文字 → UnifiedMessage                           |
  +---------------------------------------------------------------+
                                  │
  +---------------------------------------------------------------+
  |              TTS Adapter ← Phase Voice NEW                       |
  |         Google TTS / Azure TTS / AWS Polly                     |
  |         UnifiedResponse.content → 語音輸出                      |
  +---------------------------------------------------------------+
                                  │
  +---------------------------------------------------------------+
  |              Voice Emotion Analyzer ← Phase Voice NEW            |
  |         音高 / 語速 / 音量 / 靜默偵測                          |
  +---------------------------------------------------------------+
                                  │
  +---------------------------------------------------------------+
  |              Input Sanitizer L2 ← Phase 1                       |
  +---------------------------------------------------------------+
                                  │
  +---------------------------------------------------------------+
  |              Prompt Injection Defense L3 ← Phase 2              |
  +---------------------------------------------------------------+
                                  |
  +---------------------------------------------------------------+
  |              PII Masking L4 ← Phase 2                          |
  +---------------------------------------------------------------+
                                  |
  +---------------------------------------------------------------+
  |              Emotion Analyzer ← Phase 2                         |
  |                    （純文字情緒分析）                            |
  +---------------------------------------------------------------+
                                  |
  +---------------------------------------------------------------+
  |              Intent Router + DST ← Phase 2                      |
  |                    （完全復用）                                  |
  +---------------------------------------------------------------+
                                  |
  +---------------------------------------------------------------+
  |              Hybrid Knowledge Layer ← Phase 2                     |
  |                    （Layer 1-4，完全復用）                       |
  +---------------------------------------------------------------+
                                  |
  +---------------------------------------------------------------+
  |              Grounding Checks L5 ← Phase 2                      |
  +---------------------------------------------------------------+
                                  |
  +---------------------------------------------------------------+
  |              Response Generator ← Phase 1                        |
  +---------------------------------------------------------------+
                                  │
  +---------------------------------------------------------------+
  |              Escalation Manager ← Phase 2                        |
  |              （轉接人類客服，電話語音同樣適用）                    |
  +---------------------------------------------------------------+
                                  │
  +---------------------------------------------------------------+
  |              Observability Layer                                 |
  |         Prometheus + Grafana + OpenTelemetry ← Phase 3           |
  +---------------------------------------------------------------+
```

---

## 與既有平台的差異

| 維度 | LINE/Telegram（Webhook） | Web（WebSocket） | 電話語音（IVR） |
|------|------------------------|------------------|----------------|
| **輸入方向** | 平台主動推送 | 客戶主動連線 | 來話被動接收 |
| **輸入格式** | 文字（Webhook） | 文字（WebSocket） | 語音（ASR 轉文字）|
| **輸出格式** | 文字（平台 API） | 文字（WebSocket） | 語音（TTS）|
| **驗證方式** | Webhook 簽名 | JWT Token | ANI 電話號碼 |
| **使用場景** | 主動發訊息 | 主動發訊息 | 被動接聽來話 |
| **依賴 Phase** | 1 | 1+2+3+Web | 1+2+3+Voice |
| **電信成本** | 無 | 無 | 有（分鐘計費）|

---

## 平台識別

### Platform Enum 擴展

```python
# Phase 1 既有：
class Platform(Enum):
    TELEGRAM = "telegram"
    LINE = "line"
    MESSENGER = "messenger"
    WHATSAPP = "whatsapp"

# Phase Web 新增：
    WEB = "web"

# Phase Voice 新增：
    VOICE = "voice"
```

### 斷言

```
斷言：Platform enum 新增 VOICE 後，
既有程式碼中 if platform == Platform.LINE 的所有分支行為不變。
Layer 1-4 處理管線完全不知道也不需要知道輸入來自哪個 platform。
```

---

## Telecom Adapter Layer（電信介面卡）

### Twilio 整合

```python
# app/voice/telecom/twilio_adapter.py
import httpx
from dataclasses import dataclass
from enum import Enum

class CallDirection(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

class CallStatus(Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    BUSY = "busy"
    FAILED = "failed"
    NO_ANSWER = "no_answer"

@dataclass(frozen=True)
class CallEvent:
    """Twilio/Vonage 來的 Call Event 統一格式"""
    call_sid: str              # Twilio CallSid
    from_number: str           # ANI（主動號碼）
    to_number: str             # DNIS（被叫號碼）
    direction: CallDirection
    status: CallStatus
    timestamp: datetime
    duration_seconds: int = 0  # 通話時長（結束時才有）

class TwilioAdapter:
    """
    Twilio Voice Webhook 整合。

    接收 Twilio 的 Webhook 事件：
    - /api/v1/voice/webhook/twilio/incoming    (POST)
    - /api/v1/voice/webhook/twilio/status       (POST)

    Twilio Webhook 驗證方式：
    - X-Twilio-Signature header（HMAC-SHA1）
    """

    def __init__(self, auth_token: str):
        self._auth_token = auth_token

    def verify_webhook(self, body: bytes, signature: str, url: str) -> bool:
        """驗證 Twilio X-Twilio-Signature"""
        import hmac
        import hashlib
        import base64
        data = url + body.decode("utf-8")
        expected = base64.b64encode(
            hmac.new(self._auth_token.encode(), data.encode(), hashlib.sha1).digest()
        ).decode()
        return hmac.compare_digest(expected, signature)

    def parse_incoming_call(self, form: dict) -> CallEvent:
        """解析 Twilio POST form 為 CallEvent"""
        return CallEvent(
            call_sid=form["CallSid"],
            from_number=self._anonymize(form["From"]),  # 脫敏
            to_number=form["To"],
            direction=CallDirection.INBOUND,
            status=CallStatus(form["CallStatus"]),
            timestamp=datetime.utcnow(),
        )

    def _anonymize(self, phone_number: str) -> str:
        """電話號碼脫敏：保留國碼 + 最後 4 碼，其餘用 *"""
        # +886912345678 → +886****5678
        if len(phone_number) > 4:
            return phone_number[:4] + "*" * (len(phone_number) - 4)
        return phone_number
```

### Webhook 端點

```yaml
paths:
  /api/v1/voice/webhook/twilio/incoming:
    post:
      summary: Twilio 來話 Webhook
      security:
        - TwilioSignatureAuth: []
      responses:
        '200':
          description: TwiML 回應（IVR 開始）
          content:
            application/xml:
              schema:
                type: string

  /api/v1/voice/webhook/twilio/status:
    post:
      summary: Twilio 通話狀態回調
      responses:
        '200':
          description: OK
```

### TwiML 回應

```python
# app/voice/telecom/twiml.py
from dataclasses import dataclass

@dataclass
class TwiMLResponse:
    """
    Twilio Markup Language (TwiML) 回應。

    Phase Voice 使用 TwiML 告訴 Twilio：
    - 播放什麼語音
    - 等待什麼輸入（DTMF / 語音）
    - 如何轉接
    """

    @staticmethod
    def say(text: str, voice: str = "alice", language: str = "zh-TW") -> str:
        return f'<Say voice="{voice}" language="{language}">{text}</Say>'

    @staticmethod
    def gather(
        num_digits: int = 1,
        timeout: int = 5,
        prompt: str = ""
    ) -> str:
        return (
            f'<Gather numDigits="{num_digits}" timeout="{timeout}">'
            f'<Say voice="alice" language="zh-TW">{prompt}</Say>'
            f'</Gather>'
        )

    @staticmethod
    def record(
        max_duration: int = 30,
        transcribe: bool = False
    ) -> str:
        return (
            f'<Record maxDuration="{max_duration}" '
            f'transcribe="{str(transcribe).lower()}"/>'
        )

    @staticmethod
    def dial(
        number: str = None,
        record: str = "false"
    ) -> str:
        children = f'<Number>{number}</Number>' if number else ""
        return f'<Dial record="{record}">{children}</Dial>'

    @staticmethod
    def hangup() -> str:
        return "<Hangup/>"

    @staticmethod
    def to_xml(*elements: str) -> str:
        body = "".join(elements)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            f'{body}'
            '</Response>'
        )
```

---

## VoicePlatformAdapter

```python
# app/voice/platform.py
from app.platform import PlatformAdapter, UnifiedMessage, Platform, MessageType

class VoicePlatformAdapter(PlatformAdapter):
    """
    Phase Voice 新增：電話語音平台適配器。

    職責：
    - 從 Call Event 提取用戶上下文
    - 將 UnifiedResponse 轉換為 TTS 語音輸出
    - 處理 DTMF 按鍵輸入
    - 脫敏電話號碼
    """

    def extract_user_context(self, call_event: CallEvent) -> dict:
        """從 Twilio Call Event 提取用戶上下文"""
        return {
            "platform": Platform.VOICE,
            "platform_user_id": call_event.from_number,  # 脫敏後
            "call_id": call_event.call_sid,
            "direction": call_event.direction.value,
        }

    def supports_message_type(self, message_type: MessageType) -> bool:
        """語音入口：支援文字（ASR 轉譯後）和 DTMF"""
        return message_type in {MessageType.TEXT, MessageType.DTMF}

    def get_capabilities(self) -> dict:
        return {
            "voice": True,
            "dtmf": True,
            "tts": True,
            "asr": True,
            "recording": False,       # Phase Voice-2 可選
            "transfer": True,          # IVR 轉接
        }

    def response_to_voice(self, response: UnifiedResponse) -> str:
        """將 UnifiedResponse.content 轉為 TTS 要說的文字"""
        # 簡單處理：直接回傳文字內容
        # 進階：SSML 標記（停頓、音調調整）
        return response.content
```

---

## IVR Flow Engine

### IVR 流程定義

```python
# app/voice/ivr.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class IVRNodeType(Enum):
    PROMPT = "prompt"        # 播放 TTS 提示，不等待輸入
    MENU = "menu"            # 播放選單，等待 DTMF 按鍵
    COLLECT = "collect"      # 播放提示，收集語音輸入（ASR）
    TRANSFER = "transfer"    # 轉接人工客服
    CONDITION = "condition"  # 條件分支
    END = "end"             # 結束通話

@dataclass
class IVRNode:
    node_id: str
    type: IVRNodeType
    prompt_text: str                    # TTS 要說的內容
    next_nodes: dict = field(default_factory=dict)  # 按鍵 → node_id 或 intent → node_id
    timeout_seconds: int = 5
    max_retries: int = 2
    # 以下為 COLLECT 專屬
    asr_model: Optional[str] = None     # whisper | google
    expected_intents: Optional[list[str]] = None  # COLLECT 模式預期意圖列表

@dataclass
class IVRFlow:
    flow_id: str
    version: int
    name: str
    nodes: dict[str, IVRNode]           # node_id → IVRNode
    entry_node_id: str                  # 起始節點

@dataclass
class IVRSession:
    """IVR 流程執行狀態"""
    call_id: str
    flow: IVRFlow
    current_node_id: str
    retry_count: int = 0
    collected_input: str = ""           # 收集到的輸入（DTMF 或 transcript）
    conversation_id: Optional[int] = None  # 關聯 conversations 表
```

### IVR Flow 範例

```
Entry
  │
  ▼
WELCOME (PROMPT) — 「您好，歡迎致電客服中心」
  │
  ▼
MAIN_MENU (MENU)
  │「請按 1 查詢訂單，按 2 查詢帳單，按 3 人工客服，請說出您的需求」
  │
  ├─[1]─→ ORDER_INQUIRY (COLLECT) — 「請說出或輸入您的訂單編號」
  │           │
  │           └─[收到輸入]─→ ORDER_RESULT (PROMPT) ─→ MAIN_MENU
  │
  ├─[2]─→ BILL_INQUIRY (COLLECT) — 「請說出或輸入您的帳單月份」
  │           │
  │           └─[收到輸入]─→ BILL_RESULT (PROMPT) ─→ MAIN_MENU
  │
  ├─[3]─→ TRANSFER_AGENT (TRANSFER) ─→ 轉接人類客服
  │
  └─[超時/無效]─→ INVALID_INPUT (PROMPT) ─→ MAIN_MENU (max 2 retries)
                      │
                      └─[max retries]─→ END
```

### IVREngine

```python
# app/voice/ivr_engine.py
class IVREngine:
    """
    IVR 流程引擎。

    職責：
    - 解析 IVRFlow 定義，維護 IVRSession 狀態
    - 遍歷節點，播放 TTS，等待用戶輸入（DTMF 或語音 ASR）
    - 處理超時、重試、跳轉
    - 將收集到的文字輸入餽給 Intent Router + DST
    """

    def __init__(
        self,
        tts: "TTSAdapter",
        asr: "ASRAdapter",
        intent_router,
        twiml: "TwiMLResponse",
    ):
        self._tts = tts
        self._asr = asr
        self._intent = intent_router
        self._twiml = twiml

    async def start(
        self,
        call_id: str,
        flow: IVRFlow,
        tts_voice: str = "alice",
        language: str = "zh-TW"
    ) -> str:
        """
        啟動 IVR 流程，回傳第一個 TwiML 指令。
        """
        session = IVRSession(
            call_id=call_id,
            flow=flow,
            current_node_id=flow.entry_node_id,
        )
        return await self._execute_node(session, tts_voice, language)

    async def handle_input(
        self,
        call_id: str,
        user_input: str,  # DTMF digit 或 ASR transcript
        input_type: str,  # "dtmf" | "asr"
    ) -> str:
        """
        處理用戶輸入（DTMF 或 ASR），回傳 TwiML 指令。
        """
        session = self._get_session(call_id)
        node = session.flow.nodes[session.current_node_id]

        # 路由到下一個節點
        if node.type == IVRNodeType.MENU:
            next_node_id = node.next_nodes.get(user_input)
            if not next_node_id:
                next_node_id = node.next_nodes.get("__timeout__")
        elif node.type == IVRNodeType.COLLECT:
            # 將 ASR transcript 送往 Intent Router
            intent = await self._intent.route(user_input)
            next_node_id = node.next_nodes.get(
                intent.top_intent,
                node.next_nodes.get("__fallback__")
            )
        else:
            next_node_id = None

        if next_node_id is None:
            return self._twiml.hangup()

        session.current_node_id = next_node_id
        session.retry_count = 0
        return await self._execute_node(session, tts_voice, language)

    async def _execute_node(
        self,
        session: IVRSession,
        tts_voice: str,
        language: str,
    ) -> str:
        node = session.flow.nodes[session.current_node_id]

        if node.type == IVRNodeType.PROMPT:
            audio_url = await self._tts.synthesize(node.prompt_text)
            return self._twiml.to_xml(
                self._twiml.say(node.prompt_text, voice=tts_voice, language=language)
            )

        elif node.type == IVRNodeType.MENU:
            return self._twiml.to_xml(
                self._twiml.gather(
                    num_digits=1,
                    timeout=node.timeout_seconds,
                    prompt=node.prompt_text,
                )
            )

        elif node.type == IVRNodeType.COLLECT:
            return self._twiml.to_xml(
                self._twiml.say(node.prompt_text, voice=tts_voice, language=language),
                # 使用 Twilio <Record> + transcription callback
                # 或者使用 <Gather> with speechRequestMode
            )

        elif node.type == IVRNodeType.TRANSFER:
            agent_number = node.next_nodes.get("__agent__")
            return self._twiml.to_xml(
                self._twiml.say("正在為您轉接客服人員，請稍候"),
                self._twiml.dial(number=agent_number),
            )

        elif node.type == IVRNodeType.END:
            return self._twiml.to_xml(
                self._twiml.say("感謝來電，再見"),
                self._twiml.hangup(),
            )

        return self._twiml.hangup()
```

---

## ASR Adapter（語音轉文字）

```python
# app/voice/asr.py
from abc import ABC, abstractmethod
import asyncio

class ASRAdapter(ABC):
    """ASR 引擎抽象介面"""

    @abstractmethod
    async def transcribe(
        self,
        audio_url: str,
        language: str = "zh-TW",
    ) -> str:
        """將音訊 URL 轉為文字，回傳 transcript"""
        ...

class WhisperASRAdapter(ASRAdapter):
    """
    Whisper 本地部署 ASR（推薦，成本最低）。

    整合方式：
    - 模型：whisper-medium 或 whisper-large-v3
    - 部署：本地 GPU 伺服器或邊緣裝置
    - API：FastAPI 封裝 /tmp/audio 檔案
    """

    def __init__(self, api_url: str, model: str = "medium"):
        self._api_url = api_url
        self._model = model

    async def transcribe(self, audio_url: str, language: str = "zh-TW") -> str:
        async with asyncio.timeout(30):
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._api_url}/transcribe",
                    json={
                        "audio_url": audio_url,
                        "language": language,
                        "model": self._model,
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["text"]

class GoogleSTTAdapter(ASRAdapter):
    """Google Cloud Speech-to-Text（高品質，雲端）"""

    def __init__(self, credentials_path: str):
        self._credentials = credentials_path

    async def transcribe(self, audio_url: str, language: str = "zh-TW") -> str:
        # Google STT streaming 或 non-streaming API
        ...
```

---

## TTS Adapter（文字轉語音）

```python
# app/voice/tts.py
from abc import ABC, abstractmethod
import base64

class TTSAdapter(ABC):
    """TTS 引擎抽象介面"""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str = "zh-TW-Standard-A",
        speaking_rate: float = 1.0,
    ) -> str:
        """將文字轉為語音，回傳音訊 URL 或 base64 編碼"""
        ...

class GoogleTTSAdapter(TTSAdapter):
    """
    Google Cloud Text-to-Speech。

    優勢：
    - 中文語音品質高（zh-TW-Wavenet-D）
    - SSML 支援（語速、語調控制）
    """

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def synthesize(
        self,
        text: str,
        voice: str = "zh-TW-Standard-A",
        speaking_rate: float = 1.0,
    ) -> str:
        # POST https://texttospeech.googleapis.com/v1/text:synthesize
        # 回傳 audioContent (base64)，儲存到 GCS 或本地 media server
        audio_content = "..."  # base64 encoded
        return f"data:audio/mp3;base64,{audio_content}"

class SSMLBuilder:
    """SSML 標記建構工具"""

    @staticmethod
    def build(
        text: str,
        rate: float = 1.0,
        pitch: float = 0.0,
    ) -> str:
        return (
            f'<speak>'
            f'<prosody rate="{rate}" pitch="{pitch}st">{text}</prosody>'
            f'</speak>'
        )

    @staticmethod
    def add_pause(duration_ms: int = 500) -> str:
        return f'<break time="{duration_ms}ms"/>'
```

---

## Voice Emotion Analyzer

```python
# app/voice/emotion.py
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class VoiceEmotionCategory(Enum):
    NEUTRAL = "neutral"
    ANGRY = "angry"
    FRUSTRATED = "frustrated"
    CONFUSED = "confused"
    SILENT = "silent"
    HURRIED = "hurried"

@dataclass(frozen=True)
class VoiceEmotionScore:
    category: VoiceEmotionCategory
    intensity: float           # 0.0 - 1.0
    pitch_avg: float
    speech_rate: float        # 字/秒
    energy: float             # 音量分貝
    silence_ratio: float      # 靜默幀比例
    timestamp: datetime

class VoiceEmotionAnalyzer:
    """
    語音情緒分析（Phase 2 文字 Emotion Analyzer 的語音版本）。

    分析維度：
    - 音高變化（Pitch）：高而不穩 → 生氣/焦慮
    - 語速（Speech Rate）：過快 → 激動，過慢 → 沮喪/困惑
    - 音量（Energy）：過大 → 生氣，過小 → 不感興趣
    - 靜默比例（Silence Ratio）：過長靜默 → 困惑或挫折

    觸發轉接規則：
    - 連續 3 次偵測到 ANGRY 或 FRUSTRATED → 建議轉人工
    - 靜默比例 > 50% 連續 2 次 → 詢問「請問需要幫忙嗎」
    - 單次通話總靜默時間 > 30 秒 → 觸發轉人工
    """

    def __init__(self, min_confidence: float = 0.7):
        self._min_confidence = min_confidence
        self._call_emotions: dict[str, list[VoiceEmotionScore]] = {}

    async def analyze(self, call_id: str, audio_url: str) -> VoiceEmotionScore:
        """
        分析一段音訊檔案（30 秒分片）的情緒。
        由 Twilio transcription callback 或定期采样觸發。
        """
        pitch, speech_rate, energy, silence_ratio = await self._extract_features(
            audio_url
        )

        category = self._classify(pitch, speech_rate, energy, silence_ratio)

        score = VoiceEmotionScore(
            category=category,
            intensity=self._compute_intensity(category, pitch, speech_rate, energy),
            pitch_avg=pitch,
            speech_rate=speech_rate,
            energy=energy,
            silence_ratio=silence_ratio,
            timestamp=datetime.utcnow(),
        )

        if call_id not in self._call_emotions:
            self._call_emotions[call_id] = []
        self._call_emotions[call_id].append(score)

        return score

    def should_escalate(self, call_id: str) -> tuple[bool, str]:
        """判斷是否應該轉接人工客服"""
        emotions = self._call_emotions.get(call_id, [])
        if len(emotions) < 2:
            return False, ""

        # 連續負面情緒 >= 3 次
        negative_count = sum(
            1 for e in emotions[-3:]
            if e.category in (VoiceEmotionCategory.ANGRY, VoiceEmotionCategory.FRUSTRATED)
        )
        if negative_count >= 3:
            return True, "voice_emotion_negative"

        # 靜默比例過高
        silent_episodes = sum(
            1 for e in emotions[-2:]
            if e.silence_ratio > 0.5
        )
        if silent_episodes >= 2:
            return True, "voice_silence_too_long"

        return False, ""

    async def _extract_features(self, audio_url: str) -> tuple:
        """從音訊提取聲學特徵（使用 librosa 或爬取的音訊分析 API）"""
        # placeholder：實際實作需要音訊處理庫
        return 0.0, 0.0, 0.0, 0.0

    def _classify(self, pitch, speech_rate, energy, silence_ratio) -> VoiceEmotionCategory:
        if silence_ratio > 0.5:
            return VoiceEmotionCategory.SILENT
        if energy > 0.8 and speech_rate > 1.3:
            return VoiceEmotionCategory.ANGRY
        if speech_rate < 0.6:
            return VoiceEmotionCategory.CONFUSED
        return VoiceEmotionCategory.NEUTRAL

    def _compute_intensity(self, category, pitch, speech_rate, energy) -> float:
        # 計算情緒強度分數
        return 0.5  # placeholder
```

---

## 電話身份驗證（Caller Authentication）

### ANI 自動識別 + IVR PIN 驗證

```python
# app/voice/auth.py
class VoiceAuthenticator:
    """
    電話場景的用戶身份驗證。

    驗證方式（由 IVR 流程決定）：
    1. ANI（主動號碼顯示）：來電號碼直接映射 unified_user_id
       - 適合已登記電話的既有用戶
       - 須配合 IVR PIN 二次驗證（防止來電顯示欺騙）

    2. IVR PIN：語音驗證密碼
       - 首次致電或 ANI 匹配失敗時觸發
       - 密碼以 argon2 儲存（Phase Web 的密碼雜湊機制復用）
       - 3 次錯誤鎖定，需透過其他管道重置

    3. 一次性 OTP（未來擴展 Phase Voice-2）
       - 透過 SMS 發送 OTP，語音朗讀驗證
    """

    def __init__(self, db):
        self._db = db

    async def authenticate_by_ani(self, caller_number: str) -> Optional[dict]:
        """
        透過 ANI（脫敏後）查詢 users 表。
        注意：使用脫敏後的號碼查詢，需要業務邏輯對應。
        """
        # 實作時：ANI 脫敏前就 Mapping Table 查詢
        # 這裡僅示意
        row = self._db.execute(
            "SELECT * FROM voice caller_mappings WHERE anonymized_number = %s",
            (caller_number,)
        )
        return row[0] if row else None

    async def authenticate_by_pin(self, user_id: str, pin: str) -> bool:
        """IVR PIN 驗證"""
        row = self._db.execute(
            "SELECT voice_pin_hash FROM users WHERE unified_user_id = %s",
            (user_id,)
        )
        if not row:
            return False
        # 復用 Phase Web 的 argon2 verify_password
        return verify_voice_pin(pin, row["voice_pin_hash"])

    async def get_or_create_voice_user(
        self,
        caller_number: str,
        authenticated: bool = False,
    ) -> dict:
        """
        來電用戶查詢或新建（anonymous user）。
        未驗證的來電以匿名用戶處理，累計互動後綁定身份。
        """
        existing = await self.authenticate_by_ani(caller_number)
        if existing:
            return existing

        # 新建 anonymous voice user
        user_id = str(uuid.uuid4())
        self._db.execute(
            """
            INSERT INTO users (unified_user_id, platform, voice_caller_number, authenticated)
            VALUES (%s, 'voice', %s, %s)
            """,
            (user_id, caller_number, authenticated)
        )
        return {"user_id": user_id, "authenticated": authenticated}
```

---

## 資料庫 Schema Phase Voice

### 新增資料表

```sql
-- ============================================================
-- 電話語音（Phase Voice 新增）
-- ============================================================

-- 通話記錄
CREATE TABLE voice_calls (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(64) UNIQUE NOT NULL,   -- Twilio CallSid
    unified_user_id UUID REFERENCES users(unified_user_id),
    caller_number VARCHAR(20),              -- 脫敏儲存（+886****5678）
    caller_region VARCHAR(10),              -- 電話號碼前綴解析
    called_number VARCHAR(20),              -- DNIS
    direction VARCHAR(10) NOT NULL,         -- inbound | outbound
    ivr_flow_id VARCHAR(32),
    ivr_flow_version INTEGER,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    answered_at TIMESTAMPTZ,                -- IVR 完成/開始對話的時間
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,               -- 總通話時長
    end_reason VARCHAR(30),                 -- completed | transferred | no_answer | failed | abandoned
    asr_provider VARCHAR(20) DEFAULT 'whisper',
    tts_provider VARCHAR(20) DEFAULT 'google',
    recording_url TEXT,                     -- 錄音 URL（可選，Phase Voice-2）
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_calls_user ON voice_calls (unified_user_id);
CREATE INDEX idx_voice_calls_started ON voice_calls (started_at);
CREATE INDEX idx_voice_calls_call_id ON voice_calls (call_id);

-- DTMF 按鍵輸入記錄
CREATE TABLE voice_dtmf_inputs (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(64) REFERENCES voice_calls(call_id),
    digit VARCHAR(8) NOT NULL,              -- 按下的鍵（0-9, *, #）
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    ivr_node_id VARCHAR(32),                -- 當時所在的 IVR 節點
    recognition_result VARCHAR(10)          -- 是否成功識別
);

CREATE INDEX idx_dtmf_call ON voice_dtmf_inputs (call_id);

-- IVR 流程版本管理
CREATE TABLE ivr_flows (
    id SERIAL PRIMARY KEY,
    flow_id VARCHAR(32) NOT NULL,
    version INTEGER NOT NULL,
    name VARCHAR(100),
    description TEXT,
    nodes JSONB NOT NULL,                  -- IVRFlow.nodes 序列化
    is_active BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES users(unified_user_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(flow_id, version)
);

CREATE INDEX idx_ivr_flow_active ON ivr_flows (flow_id, is_active)
    WHERE is_active = TRUE;

-- 語音情緒歷史
CREATE TABLE voice_emotion_history (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(64) REFERENCES voice_calls(call_id),
    segment_start TIMESTAMPTZ,
    segment_end TIMESTAMPTZ,
    emotion_category VARCHAR(20),
    intensity FLOAT,                       -- 0.0 - 1.0
    pitch_avg FLOAT,
    speech_rate FLOAT,                     -- 字/秒
    energy FLOAT,
    silence_ratio FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_emotion_call ON voice_emotion_history (call_id);

-- 來電者電話號碼映射（脫敏前映射，內部使用）
CREATE TABLE voice_caller_mappings (
    id SERIAL PRIMARY KEY,
    raw_caller_number VARCHAR(20) UNIQUE NOT NULL,  -- 原始號碼（加嚴格存取控制）
    anonymized_number VARCHAR(20) NOT NULL,        -- 脫敏號碼（+886****5678）
    unified_user_id UUID REFERENCES users(unified_user_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ
);

-- 來電者 PIN（可選，用於 IVR PIN 驗證）
ALTER TABLE users
  ADD COLUMN voice_pin_hash VARCHAR(255);           -- argon2 hash
```

### Schema 不影響既有用戶表的聲明

```
斷言：Phase Voice 的 Schema 擴展完全隔離。
voice_calls、voice_dtmf_inputs、ivr_flows、voice_emotion_history 皆為獨立新表，
不修改任何既有的 Phase 1-3 或 Phase Web Schema。
users 表僅新增一個可選的 voice_pin_hash 欄位（可 NULL）。
```

---

## Rate Limiting（電話專屬）

```python
# app/voice/rate_limit.py
class VoiceRateLimiter:
    """
    電話流量專屬限速。

    與 Phase 1 RateLimiter 的差異：
    - 限制維度是電話號碼而非 platform_user_id
    - 多了時長維度（分鐘計費）
    - 使用 Redis 計數（通話分鐘數昂貴）
    """

    MAX_CALLS_PER_DAY = 10          # 每個電話號碼每天最多 10 通
    MAX_CALL_DURATION_MINUTES = 10  # 每通電話最長 10 分鐘（超時自動掛斷）
    COOLING_PERIOD_MINUTES = 1      # 掛斷後 1 分鐘才能再次撥入

    def __init__(self, redis_client):
        self._redis = redis_client

    async def check_incoming_call(self, caller_number: str) -> tuple[bool, str]:
        """
        檢查是否可以接通這通來話。
        回傳 (allowed, reason)
        """
        today_key = f"voice:calls:today:{caller_number}"
        cooldown_key = f"voice:cooldown:{caller_number}"

        # 冷卻期檢查
        if await self._redis.exists(cooldown_key):
            return False, "cooldown"

        # 今日通話次數
        calls_today = await self._redis.get(today_key)
        if calls_today and int(calls_today) >= self.MAX_CALLS_PER_DAY:
            return False, "daily_limit"

        return True, ""

    async def on_call_started(self, caller_number: str) -> None:
        today_key = f"voice:calls:today:{caller_number}"
        await self._redis.incr(today_key)
        await self._redis.expire(today_key, 86400)  # 24hr TTL

    async def on_call_ended(self, caller_number: str) -> None:
        cooldown_key = f"voice:cooldown:{caller_number}"
        await self._redis.setex(cooldown_key, self.COOLING_PERIOD_MINUTES * 60, "1")
```

---

## 錯誤碼擴展（Phase Voice）

| 錯誤碼 | HTTP Status | 說明 |
|--------|-------------|------|
| 既有錯誤碼 | — | Phase 1-3 既有 8 個錯誤碼不變 |
| `VOICE_CALL_FAILED` | 500 | 來話處理失敗 |
| `VOICE_ASR_ERROR` | 500 | 語音轉文字失敗 |
| `VOICE_TTS_ERROR` | 500 | 文字轉語音失敗 |
| `VOICE_NO_ANSWER` | 200 | 來話未接聽 |
| `VOICE_IVR_TIMEOUT` | 200 | IVR 無輸入超時 |
| `VOICE_DTMF_INVALID` | 200 | DTMF 無效按鍵 |
| `VOICE_RATE_LIMITED` | 429 | 超出來話頻率限制 |

---

## Observability — Prometheus 新增 Metrics

```yaml
# Phase 3 Prometheus metrics 新增 Phase Voice

  - name: omnibot_voice_calls_total
    type: counter
    labels: [direction, end_reason]
    # direction: inbound | outbound
    # end_reason: completed | transferred | no_answer | failed | abandoned

  - name: omnibot_voice_call_duration_seconds
    type: histogram
    labels: [direction]
    buckets: [30, 60, 120, 180, 240, 300]

  - name: omnibot_voice_ivr_completion_ratio
    type: gauge
    description: IVR 完成率（不走轉接就掛斷的比例）

  - name: omnibot_voice_asr_errors_total
    type: counter
    labels: [provider]
    # provider: whisper | google

  - name: omnibot_voice_tts_errors_total
    type: counter
    labels: [provider]

  - name: omnibot_voice_emotion_escalations_total
    type: counter
    labels: [reason]
    # reason: voice_emotion_negative | voice_silence_too_long

  - name: omnibot_voice_dtmf_inputs_total
    type: counter
    labels: [digit]
```

### Grafana Dashboard 新增

```
Panel: 來話量趨勢（24 小時，分鐘級）
Panel: IVR 完成率 vs 轉人工率（Pie chart）
Panel: 平均通話時長（Histogram）
Panel: ASR 錯誤率（Line chart）
Panel: 情緒分析 — ANGRY 比例（Stacked area）
Panel: DTMF 按鍵分佈（Heatmap）
Panel: 每小時接通率（Gauge）
```

---

## 部署架構 Phase Voice

### Docker Compose（Phase Voice 增量）

```yaml
# Phase 3 docker-compose.yml 新增以下服務：

services:
  omnibot-api:
    environment:
      - VOICE_ENABLED=true
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
      - ASR_PROVIDER=whisper
      - ASR_API_URL=http://whisper-asr:9000
      - TTS_PROVIDER=google
      - GOOGLE_TTS_API_KEY=${GOOGLE_TTS_API_KEY}
      - IVR_FLOW_DEFAULT=default
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8002:8002"   # Twilio webhook 接收（HTTP）

  whisper-asr:
    image: openai/whisper-large-v3
    ports:
      - "9000:9000"
    volumes:
      - ./models:/root/.cache/whisper
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # Twilio Account SID + Auth Token 僅用於驗證，
  # 實際語音傳輸由 Twilio 雲端處理（不需要自建媒體伺服器）
```

### Twilio 設定

```yaml
# Twilio Console 設定：

Voice Webhook URL (incoming calls):
  POST https://omnibot.example.com/api/v1/voice/webhook/twilio/incoming

Status Callback URL:
  POST https://omnibot.example.com/api/v1/voice/webhook/twilio/status

TTS Engine: Google Cloud Text-to-Speech
ASR Engine: Whisper (本地部署)

# TwiML 方向：
Twilio → 來話 → 送往 OmniBot Webhook → OmniBot 回 TwiML → Twilio 播放語音
```

---

## 與 Phase 2-3 既有機制的整合點對照

| 既有模組 | 整合方式 | 需修改 |
|---------|---------|--------|
| Platform enum | + VOICE 成員 | 否（新增枚舉值） |
| UnifiedMessage | platform=VOICE 直接復用 | 否 |
| HybridKnowledgeLayer | 完全直接復用 | 否 |
| InputSanitizer | 直接復用（ASR 轉文字後） | 否 |
| PIIMasking | 直接復用（電話號碼脫敏在 Telecom Adapter 處理） | 否 |
| Emotion Analyzer（文字） | 直接復用（文字情緒） | 否 |
| VoiceEmotionAnalyzer | 新增（語音情緒） | 否（新增類別） |
| Intent Router + DST | 直接復用（IVR COLLECT 節點餽文字給 DST） | 否 |
| Grounding Checks | 直接復用 | 否 |
| EscalationManager | 直接復用（TRANSFER 節點觸發） | 否 |
| conversations 表 | 直接復用，platform=VOICE | 否 |
| messages 表 | 直接復用 | 否 |
| RateLimiter | 新增 VoiceRateLimiter | 否（新增類別） |
| RBAC | web_agent 角色可擴充 voice 許可 | 否（可擴充） |
| Redis Streams | Phase 3 AsyncMessageProcessor 處理 voice queue | 否 |
| Prometheus Metrics | + omnibot_voice_* metrics | 否（擴展） |
| Structured Logger | 直接復用 | 否 |

---

## 開發任務 Phase Voice

### Phase Voice：IVR 電話語音入口（4-6 週）

- [ ] `voice_calls` 資料表建立
- [ ] `voice_dtmf_inputs` 資料表建立
- [ ] `ivr_flows` 資料表建立
- [ ] `voice_emotion_history` 資料表建立
- [ ] `voice_caller_mappings` 資料表建立
- [ ] `users` 表新增 `voice_pin_hash` 欄位
- [ ] `TwilioAdapter`（Webhook 接收 + 驗證）
- [ ] `TwiMLResponse`（TwiML 回應建構工具）
- [ ] `VoicePlatformAdapter`
- [ ] `VoiceAuthenticator`（ANI + IVR PIN 驗證）
- [ ] `ASRAdapter` ABC + `WhisperASRAdapter` 實現
- [ ] `TTSAdapter` ABC + `GoogleTTSAdapter` 實現
- [ ] `SSMLBuilder`
- [ ] `IVREngine`（IVR 流程執行器）
- [ ] `IVRFlow` + `IVRNode` 資料結構
- [ ] `VoiceCallOrchestrator`（通話生命週期管理）
- [ ] `VoiceEmotionAnalyzer`（語音情緒分析）
- [ ] `VoiceRateLimiter`（來話頻率限制）
- [ ] POST `/api/v1/voice/webhook/twilio/incoming`
- [ ] POST `/api/v1/voice/webhook/twilio/status`
- [ ] `omnibot_voice_*` Prometheus metrics
- [ ] Grafana Phase Voice Dashboard
- [ ] Docker Compose Phase Voice 增量（Whisper ASR）
- [ ] IVR Flow 管理 API（新增/編輯/版本化 IVR 流程）

---

## 驗收標準 Phase Voice

| KPI | 目標 | 測試方法 |
|-----|------|----------|
| 語音 FCR | >= 70% | SQL：platform=VOICE filter，Layer 1-4 回覆且滿意 |
| IVR 完成率 | >= 80% | (completed - transferred) / completed |
| 平均通話時長 | < 4 分鐘 | AVG(duration_seconds) WHERE ended_at IS NOT NULL |
| ASR WER | < 10% | 抽樣人工校對 transcribed text |
| 來話接通率 | >= 98% | (answered + completed) / total calls |
| Rate Limit 命中率 | — | omnibot_voice_rate_limited_total > 0 |
| 情緒轉接觸發 | 正常運作 | omnibot_voice_emotion_escalations_total > 0 |

---

## 與 Phase Voice-2 的橋接

若 Phase Voice 完成後需要擴展，建議方向（Phase Voice-2 候選）：

| 功能 | 說明 |
|------|------|
| 即時語音對話（真人般對話） | 雙向即時 ASR/TTS，打斷處理，WebRTC/RTP 串流 |
| 錄音與回放 | 通話錄音供人工複聽，需合規（GDPR/個資法） |
| 跨IVR + 文字的統一客服 | 同一用戶從電話來的可以跨管道看到對話歷史 |
| 預測式轉接 | 根據來電者 ANI 預先載入上下文 |
| 多語言語音支援 | 台語、客語、英語等多語言 IVR |
| 電話外撥（Outbound） | 主動致電用戶通知（如貨態通知） |

---

*Phase: Voice*  
*文件版本: v1.0*  
*最後更新: 2026-05-01*
