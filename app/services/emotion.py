"""Unified Emotion Module - Phase 2"""
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List


class EmotionCategory(Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass(frozen=True)
class EmotionScore:
    category: EmotionCategory
    intensity: float  # 0.0 - 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EmotionTracker:
    """Emotion tracker with temporal decay (Phase 2)"""
    
    def __init__(self, history: List[EmotionScore] = None, half_life_hours: float = 24.0):
        self.history = history or []
        self.half_life_hours = half_life_hours

    def add(self, score: EmotionScore) -> None:
        """Add a new emotion score to history"""
        self.history.append(score)

    def current_weighted_score(self) -> float:
        """Calculate weighted emotion score with exponential decay"""
        now = datetime.utcnow()
        total_weight = 0.0
        weighted_sum = 0.0

        for score in self.history:
            hours_ago = (now - score.timestamp).total_seconds() / 3600
            decay = math.exp(-0.693 * hours_ago / self.half_life_hours)

            # Positive contributes +, Negative contributes -
            raw = score.intensity if score.category == EmotionCategory.POSITIVE else -score.intensity
            if score.category == EmotionCategory.NEUTRAL:
                raw = 0.0
                
            weighted_sum += raw * decay
            total_weight += decay

        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight

    def consecutive_negative_count(self) -> int:
        """Count consecutive negative emotions from most recent"""
        count = 0
        for score in reversed(self.history):
            if score.category == EmotionCategory.NEGATIVE:
                count += 1
            else:
                break
        return count

    def should_escalate(self) -> bool:
        """Determine if escalation is needed based on negative emotions"""
        return self.consecutive_negative_count() >= 3
