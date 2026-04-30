"""i18n Expansion Roadmap - Phase 3"""

class ExpansionRoadmap:
    """Roadmap for multi-language support"""
    def __init__(self):
        self.languages = ["zh-TW", "en", "zh-CN", "ja"]
        self.supported_languages = self.languages
        self.deployed_languages = ["zh-TW", "en"]

EXPANSION_ROADMAP = ExpansionRoadmap()
