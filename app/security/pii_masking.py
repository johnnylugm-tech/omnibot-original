"""PII masking - L4 basic PII de-identification"""
import re
from typing import List

from app.models import PIIMaskResult


class PIIMasking:
    """
    Basic PII de-identification (Phase 1).
    Scope: Taiwan formats only (phone, address, email).
    Phase 2: Credit card Luhn validation.
    """

    # Taiwan phone patterns: 0912-345-678, 0912345678, 02-1234-5678
    PATTERNS = {
        "phone": re.compile(
            r"\b(?:\d{4}-\d{3,4}-\d{3,4}|\d{10,11})\b"
        ),
        "email": re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        ),
        "address": re.compile(
            r"(?:(?:台|臺)(?:北|中|南|東)?|新北|桃園|高雄|基隆|新竹|嘉義|"
            r"苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|澎湖|金門|連江)"
            r"(?:市|縣).{2,30}?(?:路|街|巷|弄|號|樓)"
        ),
    }

    # Sensitive keywords that trigger escalation
    SENSITIVE_KEYWORDS: List[re.Pattern] = [
        re.compile(r"密碼"),
        re.compile(r"銀行帳戶"),
        re.compile(r"信用卡號"),
        re.compile(r"提款卡"),
    ]

    def mask(self, text: str) -> PIIMaskResult:
        """Mask PII in text"""
        masked = text
        count = 0
        pii_types: List[str] = []

        for pii_type, pattern in self.PATTERNS.items():
            matches = list(pattern.finditer(masked))
            for match in reversed(matches):
                start, end = match.start(), match.end()
                masked = masked[:start] + f"[{pii_type}_masked]" + masked[end:]
                count += 1
                if pii_type not in pii_types:
                    pii_types.append(pii_type)

        return PIIMaskResult(
            masked_text=masked,
            mask_count=count,
            pii_types=pii_types
        )

    def should_escalate(self, text: str) -> bool:
        """Check if text contains sensitive keywords"""
        return any(p.search(text) for p in self.SENSITIVE_KEYWORDS)
