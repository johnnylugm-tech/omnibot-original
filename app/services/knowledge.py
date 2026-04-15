"""Knowledge Layer Phase 1 - Rule matching only"""
from typing import Optional, List
from app.models import KnowledgeResult


class KnowledgeLayerV1:
    """Phase 1: Rule matching + escalation fallback"""

    def __init__(self, db):
        self.db = db

    def query(self, query_text: str) -> KnowledgeResult:
        result = self._rule_match(query_text)
        if result is not None and result.confidence > 0.7:
            return result
        return self._escalate(query_text, reason="no_rule_match")

    def _rule_match(self, query_text: str) -> Optional[KnowledgeResult]:
        results = self._rule_match_list(query_text)
        return results[0] if results else None

    def _rule_match_list(self, query_text: str) -> List[KnowledgeResult]:
        return []

    def _escalate(self, query_text: str, reason: str) -> KnowledgeResult:
        return KnowledgeResult(
            id=-1,
            content="正在為您轉接人工客服，請稍候...",
            confidence=0.0,
            source="escalate",
        )
