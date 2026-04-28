"""
Atomic TDD Tests for Phase 2: Grounding Checks L5 (#20)
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.grounding import GroundingChecker

@pytest.fixture
def checker():
    # Mock the SentenceTransformer to avoid downloading model during tests
    with patch("app.services.grounding.SentenceTransformer") as mock_model:
        instance = GroundingChecker()
        instance.model = mock_model.return_value
        yield instance

def test_grounding_check_grounded_above_threshold(checker):
    """similarity >= 0.75 → grounded=True"""
    # Mock embeddings such that cosine similarity is high (e.g., 0.8)
    # Cosine similarity = dot(a, b) / (norm(a) * norm(b))
    checker.model.encode.side_effect = [
        [1.0, 0.0], # Response
        [[0.8, 0.6]] # Source (dot product = 0.8, both norms = 1.0)
    ]
    
    result = checker.check("Response text", ["Source text"])
    assert result["grounded"] is True
    assert result["score"] >= 0.75

def test_grounding_check_not_grounded_below_threshold(checker):
    """similarity < 0.75 → grounded=False"""
    checker.model.encode.side_effect = [
        [1.0, 0.0], # Response
        [[0.5, 0.866]] # Source (dot product = 0.5)
    ]
    
    result = checker.check("Response text", ["Source text"])
    assert result["grounded"] is False
    assert result["score"] < 0.75

def test_grounding_check_returns_best_match_index(checker):
    """Verify best_match_index is returned correctly"""
    checker.model.encode.side_effect = [
        [1.0, 0.0], # Response
        [[0.1, 0.99], [0.9, 0.43]] # Source 1 (low), Source 2 (high)
    ]
    
    result = checker.check("Response", ["Low match", "High match"])
    assert result["best_match_index"] == 1

def test_grounding_check_no_source_text_returns_false(checker):
    """Empty sources → grounded=False"""
    result = checker.check("Response", [])
    assert result["grounded"] is False
    assert result["score"] == 0.0

def test_grounding_check_returns_score(checker):
    """Result includes score field"""
    checker.model.encode.side_effect = [
        [1.0, 0.0],
        [[0.8, 0.6]]
    ]
    result = checker.check("Response", ["Source"])
    assert "score" in result
    assert isinstance(result["score"], float)

def test_grounding_check_threshold_configurable():
    """Threshold can be customized"""
    with patch("app.services.grounding.SentenceTransformer"):
        checker = GroundingChecker(threshold=0.9)
        checker.model.encode.side_effect = [
            [1.0, 0.0],
            [[0.85, 0.52]] # Score 0.85 < 0.9
        ]
        result = checker.check("Response", ["Source"])
        assert result["grounded"] is False

def test_grounding_check_uses_correct_embedding_model():
    """Default model is paraphrase-multilingual-MiniLM-L12-v2"""
    with patch("app.services.grounding.SentenceTransformer") as mock_transformer:
        checker = GroundingChecker()
        mock_transformer.assert_called_once_with("paraphrase-multilingual-MiniLM-L12-v2")
