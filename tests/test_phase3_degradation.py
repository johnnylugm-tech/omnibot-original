"""
Atomic TDD Tests for Phase 3: Degradation Strategy (#36)
Focus: Latency-based and Failure-based service level switching.
"""
import pytest
from app.services.degradation import DegradationManager, DegradationLevel

@pytest.fixture
def manager():
    return DegradationManager()

def test_id_36_01_llm_latency_triggers_level_1(manager):
    """LLM p95 > 3s -> Level 1 (RAG Only)"""
    manager.update_metrics(llm_latency=3.5)
    assert manager.current_level == DegradationLevel.LEVEL_1
    layers = manager.get_allowed_layers()
    assert layers["rule"] is True
    assert layers["rag"] is True
    assert layers["llm"] is False

def test_id_36_02_llm_failure_triggers_level_2(manager):
    """LLM failure > 3 times -> Level 2 (Rule Only)"""
    for _ in range(4):
        manager.update_metrics(llm_success=False)
    
    assert manager.current_level == DegradationLevel.LEVEL_2
    layers = manager.get_allowed_layers()
    assert layers["rule"] is True
    assert layers["rag"] is False
    assert layers["llm"] is False

def test_id_36_03_db_latency_triggers_level_3(manager):
    """DB p95 > 2s -> Level 3 (Read-only Cache)"""
    manager.update_metrics(db_latency=2.5)
    assert manager.current_level == DegradationLevel.LEVEL_3
    layers = manager.get_allowed_layers()
    assert layers.get("cache_only") is True

def test_id_36_04_recovery_on_success(manager):
    """Success after failure resets to Level 0"""
    for _ in range(4):
        manager.update_metrics(llm_success=False)
    assert manager.current_level == DegradationLevel.LEVEL_2
    
    manager.update_metrics(llm_success=True)
    assert manager.current_level == DegradationLevel.LEVEL_0
