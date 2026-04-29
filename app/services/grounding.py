import numpy as np
from typing import List, Dict, Any, Union
from sentence_transformers import SentenceTransformer

class GroundingChecker:
    DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
    def __init__(self, threshold: float = 0.75, model_name: str = None):
        self.threshold = threshold
        self.model = SentenceTransformer(model_name or self.DEFAULT_MODEL)

    def check(self, response: Any, sources: List[Any]) -> Dict[str, Any]:
        resp_text = response.content if hasattr(response, 'content') else str(response)
        src_texts = [s.content if hasattr(s, 'content') else str(s) for s in sources]
        
        if not src_texts:
            return {"grounded": False, "score": 0.0, "best_match_index": -1, "reason": "no_sources"}
        
        response_emb = self.model.encode(resp_text)
        source_embs = self.model.encode(src_texts)
        
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            
        scores = [cosine_similarity(response_emb, s_emb) for s_emb in source_embs]
        best_score = max(scores)
        return {
            "grounded": bool(best_score >= self.threshold),
            "score": float(best_score),
            "best_match_index": int(scores.index(best_score))
        }
