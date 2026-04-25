import pytest
from app.security.pii_masking import PIIMasking
from app.security.rate_limiter import RateLimiter, TokenBucket
import time

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
