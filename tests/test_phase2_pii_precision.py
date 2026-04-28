"""
Atomic TDD Tests for Phase 2: PII Precision & False Positive Defense (#16)
Focus: Amex (15-digit) support, Luhn validation for multiple card lengths, 
and preventing false positives for non-card numbers.
"""
import pytest
from app.security.pii_masking import PIIMasking

@pytest.fixture
def masker():
    return PIIMasking()

def test_id_16_01_amex_15_digit_support(masker):
    """Amex 15-digit card (passes Luhn) -> masked"""
    # Amex: 378282246310005 (valid)
    text = "My Amex is 3782-822463-10005"
    result = masker.mask(text)
    assert "[credit_card_masked]" in result.masked_text
    
    # Without dashes
    text2 = "Amex 378282246310005"
    result2 = masker.mask(text2)
    assert "[credit_card_masked]" in result2.masked_text

def test_id_16_02_luhn_failure_no_mask(masker):
    """Valid length but fails Luhn -> NOT masked"""
    # 16 digits, fails Luhn: 4111111111111112
    text = "This is not a card: 4111111111111112"
    result = masker.mask(text)
    assert "4111111111111112" in result.masked_text
    assert "[credit_card_masked]" not in result.masked_text

def test_id_16_03_various_card_lengths(masker):
    """Support 13 to 19 digit cards (Visa, Mastercard, etc.)"""
    # 13 digits (Visa legacy) - 4111111111119 (valid)
    text13 = "Visa 13: 4111111111119"
    assert "[credit_card_masked]" in masker.mask(text13).masked_text
    
    # 19 digits (UnionPay etc.) - 6221261234567890129 (valid)
    text19 = "UnionPay 19: 6221261234567890129"
    assert "[credit_card_masked]" in masker.mask(text19).masked_text

def test_id_16_04_overlapping_pii_types(masker):
    """Ensure card-like phone numbers or ID numbers don't conflict"""
    # A Taiwan mobile number 0912345678 (10 digits) should NOT be masked as credit card
    text = "My phone is 0912345678"
    result = masker.mask(text)
    assert "[phone_masked]" in result.masked_text
    assert "[credit_card_masked]" not in result.masked_text
