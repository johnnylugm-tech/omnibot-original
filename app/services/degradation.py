from typing import Optional
"""
Degradation Manager - Phase 3 Resilience
Handles automatic service level switching based on performance and failure metrics.
"""
from enum import IntEnum
from typing import Dict, Any


class DegradationLevel(IntEnum):
    LEVEL_0 = 0  # Full Service (Rule + RAG + LLM)
    LEVEL_1 = 1  # RAG Only (Rule + RAG, no LLM generation)
    LEVEL_2 = 2  # Rule Only (Layer 1 only)
    LEVEL_3 = 3  # Read-only Cache (DB pressure)
    LEVEL_4 = 4  # Maintenance Mode (Total outage)


class DegradationManager:
    """
    Manager to monitor metrics and determine the current service level.
    Follows Spec ID 36.
    """

    def __init__(self):
        self.current_level = DegradationLevel.LEVEL_0
        self.llm_failure_count = 0
        self.db_latency_p95 = 0.0
        self.llm_latency_p95 = 0.0

    def update_metrics(self, llm_latency: Optional[float] = None, llm_success: Optional[bool] = None, db_latency: Optional[float] = None):
        """Update system metrics and recalculate degradation level"""
        if llm_latency is not None:
            self.llm_latency_p95 = llm_latency  # Simple tracking for TDD

        if llm_success is False:
            self.llm_failure_count += 1
        elif llm_success is True:
            self.llm_failure_count = 0  # Reset on success

        if db_latency is not None:
            self.db_latency_p95 = db_latency

        # Determine level
        if self.llm_failure_count > 3:
            self.current_level = DegradationLevel.LEVEL_2
        elif self.llm_latency_p95 > 3.0:
            self.current_level = DegradationLevel.LEVEL_1
        elif self.db_latency_p95 > 2.0:
            self.current_level = DegradationLevel.LEVEL_3
        else:
            self.current_level = DegradationLevel.LEVEL_0

    def get_allowed_layers(self) -> Dict[str, bool]:
        """Returns which layers are currently active"""
        if self.current_level == DegradationLevel.LEVEL_0:
            return {"rule": True, "rag": True, "llm": True}
        if self.current_level == DegradationLevel.LEVEL_1:
            return {"rule": True, "rag": True, "llm": False}
        if self.current_level == DegradationLevel.LEVEL_2:
            return {"rule": True, "rag": False, "llm": False}
        if self.current_level == DegradationLevel.LEVEL_3:
            return {"rule": True, "rag": False, "llm": False, "cache_only": True}
        return {"maintenance": True}
