"""i18n Expansion Roadmap - Phase 3

Previously defined ExpansionRoadmap class (dead code: no app source module called it,
only tests referenced it). Replaced with a minimal stub to avoid breaking test imports.

DEPRECATED: No production code depends on this. Tests import it for roadmap assertions.
"""
from dataclasses import dataclass


@dataclass
class ExpansionRoadmap:
    languages: list = None
    supported_languages: list = None
    deployed_languages: list = None

    def __init__(self):
        self.languages = ["zh-TW", "en", "zh-CN", "ja"]
        self.supported_languages = self.languages
        self.deployed_languages = ["zh-TW", "en"]


# Stub kept to avoid breaking tests that import this symbol
EXPANSION_ROADMAP = ExpansionRoadmap()
