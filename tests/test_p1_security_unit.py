import pytest
from app.security.input_sanitizer import InputSanitizer
from app.security.pii_masking import PIIMasking

@pytest.fixture
def sanitizer():
    return InputSanitizer()

@pytest.fixture
def pii_masker():
    return PIIMasking()

# 2.2 Phase 1 驗證矩陣 - L2 InputSanitizer
class TestInputSanitizer:
    def test_normal_text(self, sanitizer):
        # NFKC normalizes full-width comma to half-width comma
        assert sanitizer.sanitize("你好，我想查訂單") == "你好,我想查訂單"

    def test_full_width_to_half_width(self, sanitizer):
        # NFKC normalizes full-width to half-width
        assert sanitizer.sanitize("ｆｕｌｌ　ｗｉｄｔｈ") == "full width"

    def test_control_character_removal(self, sanitizer):
        assert sanitizer.sanitize("hello\x00world") == "helloworld"

    def test_whitespace_preservation(self, sanitizer):
        # Newlines and tabs should be kept
        text = "line1\nline2\tgap"
        assert sanitizer.sanitize(text) == text

    def test_emoji_preservation(self, sanitizer):
        assert sanitizer.sanitize("😀表情") == "😀表情"

# 2.2 Phase 1 驗證矩陣 - L4 PII Masking
class TestPIIMasking:
    def test_taiwan_phone_dashed(self, pii_masker):
        res = pii_masker.mask("聯絡我 0912-345-678")
        assert res.masked_text == "聯絡我  [phone_masked]"
        assert res.mask_count == 1
        assert "phone" in res.pii_types

    def test_taiwan_phone_10_digits(self, pii_masker):
        res = pii_masker.mask("聯絡我 0912345678")
        assert res.masked_text == "聯絡我  [phone_masked]"
        assert res.mask_count == 1

    def test_email_masking(self, pii_masker):
        res = pii_masker.mask("email: john@test.com")
        assert res.masked_text == "email:  [email_masked]"
        assert res.mask_count == 1

    def test_taiwan_address_masking(self, pii_masker):
        # Based on PATTERNS in pii_masking.py
        res = pii_masker.mask("送至台中市北區進化路123號")
        assert res.masked_text == "送至 [address_masked]"
        assert res.mask_count == 1

    def test_sensitive_keyword_escalation(self, pii_masker):
        assert pii_masker.should_escalate("我的密碼是 1234") is True
        assert pii_masker.should_escalate("正常詢問") is False

    def test_multiple_pii_mixed(self, pii_masker):
        text = "王先生 0912-345-678 email@test.com"
        res = pii_masker.mask(text)
        assert "[phone_masked]" in res.masked_text
        assert "[email_masked]" in res.masked_text
        assert res.mask_count == 2

    def test_credit_card_luhn_valid(self, pii_masker):
        # Valid visa card number (Luhn pass)
        res = pii_masker.mask("我的卡號是 4111-1111-1111-1111")
        assert "[credit_card_masked]" in res.masked_text
        assert res.mask_count == 1

    def test_credit_card_luhn_invalid(self, pii_masker):
        # Luhn fail
        res = pii_masker.mask("我的卡號是 4111-1111-1111-1112")
        assert "4111-1111-1111-1112" in res.masked_text
        assert res.mask_count == 0

# 2.2 Phase 1 驗證矩陣 - Rate Limiter
import time
from app.security.rate_limiter import TokenBucket, RateLimiter

class TestRateLimiter:
    def test_token_bucket_consumption(self):
        bucket = TokenBucket(capacity=2, refill_rate=1.0)
        assert bucket.consume(1) is True
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False

    def test_token_bucket_refill(self):
        bucket = TokenBucket(capacity=1, refill_rate=10.0)
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False
        time.sleep(0.15) # Wait for ~1.5 tokens
        assert bucket.consume(1) is True

    def test_rate_limiter_factory(self):
        limiter = RateLimiter(default_rps=5)
        assert limiter.check("telegram", "user1") is True
        for _ in range(4):
            limiter.check("telegram", "user1")
        assert limiter.check("telegram", "user1") is False
        assert limiter.check("line", "user1") is True # Different key

# 2.2 Phase 1 驗證矩陣 - Webhook Verifier
from app.security.webhook_verifier import get_verifier
import hashlib
import hmac
import base64

class TestWebhookVerifier:
    def test_telegram_verification(self):
        token = "test_token"
        verifier = get_verifier("telegram", token)
        body = b"hello world"
        
        # Calculate correct signature
        secret_key = hashlib.sha256(token.encode("utf-8")).digest()
        signature = hmac.new(secret_key, body, hashlib.sha256).hexdigest()
        
        assert verifier.verify(body, signature) is True
        assert verifier.verify(body, "wrong_sig") is False

    def test_line_verification(self):
        secret = "test_secret"
        verifier = get_verifier("line", secret)
        body = b"hello line"
        
        # Calculate correct signature
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        signature = base64.b64encode(digest).decode("utf-8")
        
        assert verifier.verify(body, signature) is True
        assert verifier.verify(body, "wrong_sig") is False

