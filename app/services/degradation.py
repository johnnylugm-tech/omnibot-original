"""
Degradation Manager - Phase 3 Resilience
Handles automatic service level switching based on performance and failure metrics.
"""

from enum import IntEnum
from typing import Dict, Optional


class DegradationLevel(IntEnum):
    LEVEL_0 = 0  # Full Service (Rule + RAG + LLM)
    LEVEL_1 = 1  # RAG Only (Rule + RAG, no LLM generation)
    LEVEL_2 = 2  # Rule Only (Layer 1 only)
    LEVEL_3 = 3  # Read-only Cache (DB pressure)
    LEVEL_4 = 4  # Maintenance Mode (Total outage)


class DegradationManager:
    """
    Manages service degradation levels based on error rates and latency.
    """

    def __init__(self, thresholds: Optional[Dict] = None):
        self.thresholds = thresholds or {
            "error_rate": 0.1,  # 10% error rate triggers degradation
            "latency_ms": 2000,  # 2s latency triggers degradation
            "consecutive_failures": 3,
        }
        self.current_level = DegradationLevel.LEVEL_0
        self.consecutive_failures = 0

    def update_metrics(
        self,
        error_rate: float = 0.0,
        latency_ms: float = 0,
        llm_latency: float = 0,
        llm_success: bool = True,
        db_latency: float = 0.0,
    ) -> DegradationLevel:
        """Update system metrics and potentially change degradation level"""
        if not llm_success:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0

        # Degradation logic (Phase 3 spec)
        if (
            self.consecutive_failures >= self.thresholds["consecutive_failures"]
            or error_rate > self.thresholds["error_rate"]
        ):
            if self.current_level < DegradationLevel.LEVEL_2:
                self.current_level = DegradationLevel.LEVEL_2
        elif db_latency > 2.0:
            self.current_level = DegradationLevel.LEVEL_3
        elif (
            llm_latency > self.thresholds["latency_ms"] / 1000.0
            and self.current_level == DegradationLevel.LEVEL_0
        ):
            self.current_level = DegradationLevel.LEVEL_1
        else:
            # Recovery logic (simplified)
            if self.consecutive_failures == 0 and error_rate < 0.05:
                self.current_level = DegradationLevel.LEVEL_0

        return self.current_level

    def get_allowed_layers(self) -> Dict[str, bool]:
        """Returns which knowledge layers are allowed at current level"""
        layers = {
            "rule": True,
            "rag": True,
            "llm": True,
            "cache_only": False,
            "maintenance": False,
        }

        if self.current_level == DegradationLevel.LEVEL_1:
            layers["llm"] = False
        elif self.current_level == DegradationLevel.LEVEL_2:
            layers["rag"] = False
            layers["llm"] = False
        elif self.current_level == DegradationLevel.LEVEL_3:
            layers["rule"] = False
            layers["rag"] = False
            layers["llm"] = False
            layers["cache_only"] = True
        elif self.current_level == DegradationLevel.LEVEL_4:
            layers["rule"] = False
            layers["rag"] = False
            layers["llm"] = False
            layers["maintenance"] = True

        return layers
