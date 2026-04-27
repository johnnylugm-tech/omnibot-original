"""i18n Translation - Phase 3"""
import os
from typing import Dict, Optional

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "zh-TW": {
        "greeting": "您好！請問有什麼可以幫您的？",
        "escalate": "正在為您轉接人工客服，請稍候...",
        "error": "抱歉，系統發生錯誤，請稍後再試。",
        "rate_limit": "請求頻率過高，請稍後再試。"
    },
    "en": {
        "greeting": "Hello! How can I help you?",
        "escalate": "Transferring to a human agent, please wait...",
        "error": "Sorry, a system error occurred. Please try again later.",
        "rate_limit": "Rate limit exceeded. Please try again later."
    }
}

class I18nManager:
    """Simple i18n manager for Phase 3"""
    def __init__(self, default_lang: str = "zh-TW"):
        self.default_lang = os.getenv("DEFAULT_LANG", default_lang)

    def translate(self, key: str, lang: Optional[str] = None) -> str:
        """Translate a key to the target language"""
        lang = lang or self.default_lang
        return TRANSLATIONS.get(lang, TRANSLATIONS["zh-TW"]).get(key, key)

# Singleton instance
i18n = I18nManager()
