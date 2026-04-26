from app.security.pii_masking import PIIMasking
from app.security.rate_limiter import RateLimiter, TokenBucket
from app.security.input_sanitizer import InputSanitizer
from app.security.webhook_verifier import LineWebhookVerifier, TelegramWebhookVerifier


def test_input_sanitizer():
    sanitizer = InputSanitizer()
    # Test normalization (NFKC)
    assert sanitizer.sanitize("Ｈｅｌｌｏ") == "Hello"
    # Test control character removal
    assert sanitizer.sanitize("Hello\x00World") == "HelloWorld"
    # Test whitespace stripping
    assert sanitizer.sanitize("  Hello  ") == "Hello"

def test_line_verifier():
    # Mock channel secret
    secret = "test_secret"
    verifier = LineWebhookVerifier(secret)
    body = b"test_body"
    # Valid signature would be HMAC-SHA256(secret, body) base64 encoded
    import hmac, hashlib, base64
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    valid_sig = base64.b64encode(digest).decode()
    
    assert verifier.verify(body, valid_sig) is True
    assert verifier.verify(body, "invalid_sig") is False

def test_telegram_verifier():
    bot_token = "test_token"
    verifier = TelegramWebhookVerifier(bot_token)
    body = b"test_body"
    import hmac, hashlib
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    valid_sig = hmac.new(secret_key, body, hashlib.sha256).hexdigest()
    
    assert verifier.verify(body, valid_sig) is True
    assert verifier.verify(body, "wrong") is False

def test_pii_masking_phone():
    masker = PIIMasking()
    text = "我的電話是 0912345678"
    result = masker.mask(text)
    assert "[phone_masked]" in result.masked_text
    assert result.mask_count == 1
    assert "phone" in result.pii_types

def test_pii_masking_email():
    masker = PIIMasking()
    text = "請寄信到 test@example.com"
    result = masker.mask(text)
    assert "[email_masked]" in result.masked_text
    assert "email" in result.pii_types

def test_pii_masking_address():
    masker = PIIMasking()
    text = "我在台北市中正區重慶南路一段122號"
    result = masker.mask(text)
    assert "[address_masked]" in result.masked_text
    assert "address" in result.pii_types

def test_pii_should_escalate():
    masker = PIIMasking()
    assert masker.should_escalate("我要修改密碼") is True
    assert masker.should_escalate("今天天氣不錯") is False

def test_token_bucket_consume():
    bucket = TokenBucket(capacity=2, refill_rate=1)
    assert bucket.consume(1) is True
    assert bucket.consume(1) is True
    assert bucket.consume(1) is False

def test_rate_limiter_per_user():
    limiter = RateLimiter(default_rps=1)
    assert limiter.check("line", "user1") is True
    assert limiter.check("line", "user1") is False
    assert limiter.check("line", "user2") is True
    assert limiter.check("line", "user2") is False
