"""
RED Gaps Verification - Phase 3
Focus: CostModel daily cap and i18n translation completeness.
"""
import pytest
from app.utils.cost_model import CostModel
from app.utils.i18n import TRANSLATIONS

def test_cost_model_respects_daily_cap():
    """test_id_30_05: CostModel.apply_daily_cap 必須正確限制每日開銷"""
    model = CostModel()
    
    # Case 1: Within cap
    assert model.apply_daily_cap(current_total=40.0, next_cost=5.0, cap=50.0) == 5.0
    
    # Case 2: Exceeds cap (partial allowed)
    # Total 48 + 5 = 53 > 50. Allowed = 50 - 48 = 2.
    assert model.apply_daily_cap(current_total=48.0, next_cost=5.0, cap=50.0) == 2.0
    
    # Case 3: Already at/over cap
    assert model.apply_daily_cap(current_total=50.0, next_cost=5.0, cap=50.0) == 0.0

def test_expansion_roadmap_zh_cn_content_exists_and_non_empty():
    """test_id_30_07: TRANSLATIONS 必須包含 zh-CN 簡體中文"""
    assert "zh-CN" in TRANSLATIONS, "TRANSLATIONS missing 'zh-CN' key"
    assert len(TRANSLATIONS["zh-CN"]) > 0
    assert "greeting" in TRANSLATIONS["zh-CN"]

def test_expansion_roadmap_ja_content_exists_and_non_empty():
    """test_id_30_08: TRANSLATIONS 必須包含 ja 日文"""
    assert "ja" in TRANSLATIONS, "TRANSLATIONS missing 'ja' key"
    assert len(TRANSLATIONS["ja"]) > 0
    assert "greeting" in TRANSLATIONS["ja"]


def test_expansion_roadmap_en_content_exists_and_non_empty():
    """test_id_30_09: TRANSLATIONS 必須包含 en 英文（用戶要求預設語言）"""
    assert "en" in TRANSLATIONS, "TRANSLATIONS missing 'en' key"
    assert len(TRANSLATIONS["en"]) > 0, "English translations must be non-empty"
    assert "greeting" in TRANSLATIONS["en"], "English must have 'greeting' key"
