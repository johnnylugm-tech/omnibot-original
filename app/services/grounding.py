"""
L5: Grounding Check Service - Phase 2
Verify LLM response against source knowledge using vector similarity.
"""
import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer


class GroundingChecker:
    """
    Grounding Checker (Phase 2) using SentenceTransformer similarity.
    Ensures LLM outputs are grounded in provided source materials.
    """
    DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, threshold: float = 0.75, model_name: str = None):
        self.threshold = threshold
        self.model = SentenceTransformer(model_name or self.DEFAULT_MODEL)

    def check(self, response_text: str, source_texts: List[str]) -> Dict[str, Any]:
        """
        Check if response_text is grounded in any of the source_texts.
        Returns a dict with grounded status, score, and best match index.
        """
        if not source_texts:
            return {
                "grounded": False,
                "score": 0.0,
                "best_match_index": -1,
                "reason": "no_source_texts"
            }

        # Encode texts
        response_emb = self.model.encode(response_text)
        source_embs = self.model.encode(source_texts)

        # Calculate cosine similarities
        # similarities = dot(response, sources) / (norm(response) * norm(sources))
        # sentence_transformers encode often returns normalized vectors, but let's be safe

        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        scores = [cosine_similarity(response_emb, s_emb)
                  for s_emb in source_embs]
        best_score = max(scores)
        best_index = scores.index(best_score)

        return {
            "grounded": bool(best_score >= self.threshold),
            "score": float(best_score),
            "best_match_index": int(best_index)
        }
