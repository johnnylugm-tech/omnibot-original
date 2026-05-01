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

    # Taiwan phone patterns, email, address, credit card, and national ID
    # Use refined regex patterns
    PATTERNS = {
        "credit_card": re.compile(
            r"(?:(?:\d[ -]*?){13,19})"
        ),
        "phone": re.compile(
            r"(?:\+886[- ]?|0)9\d{2}[- ]?\d{3}[- ]?\d{3}"
        ),
        "email": re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        ),
        "address": re.compile(
            r"(?:(?:台|臺)(?:北|中|南|東)?|新北|桃園|高雄|基隆|新竹|嘉義|"
            r"苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|澎湖|金門|連江)"
            r"(?:市|縣).{2,30}?(?:路|街|巷|弄|號|樓)"
        ),
        "national_id": re.compile(r"\b[A-Z][12]\d{8}\b"),
    }

    SENSITIVE_KEYWORDS: List[re.Pattern] = [
        re.compile(r"密碼"),
        re.compile(r"銀行帳戶"),
        re.compile(r"信用卡號"),
        re.compile(r"提款卡"),
    ]

    def mask(self, text: str) -> PIIMaskResult:
        """Mask PII in text with Luhn validation for credit cards"""
        masked = text
        found_types = set()
        total_count = 0

        # Process each PII type
        # We process credit_card separately to ensure Luhn check is applied correctly
        for pii_type, pattern in self.PATTERNS.items():
            def replacer(match):
                nonlocal total_count
                val = match.group()
                if pii_type == "credit_card":
                    if not self._luhn_check(val):
                        return val
                
                total_count += 1
                found_types.add(pii_type)
                return f"[{pii_type}_masked]"

            masked = pattern.sub(replacer, masked)

        return PIIMaskResult(
            masked_text=masked,
            mask_count=total_count,
            pii_types=sorted(list(found_types))
        )

    def should_escalate(self, text: str) -> bool:
        """Check if text contains sensitive keywords"""
        return any(p.search(text) for p in self.SENSITIVE_KEYWORDS)

    @staticmethod
    def _luhn_check(card_number: str) -> bool:
        """Luhn algorithm validation for credit card numbers"""
        digits = [int(d) for d in card_number if d.isdigit()]
        if len(digits) < 13 or len(digits) > 19:
            return False

        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        return checksum % 10 == 0
