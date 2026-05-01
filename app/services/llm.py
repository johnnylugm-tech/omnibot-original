"""LLM Service - Phase 3"""
import os
from typing import Any, Optional

class LLMService:
    """Mockable LLM service for testing and production"""
    def __init__(self, model_name: Optional[str] = None):
        # Env-aware model name
        self.model_name = model_name or os.getenv("LLM_MODEL_PROD", os.getenv("LLM_MODEL", "gpt-4"))
        self.base_prompt = self._load_base_prompt()
        
    def _load_base_prompt(self) -> str:
        """Load Layer 3 base prompt from env or file config"""
        prompt = os.getenv("LLM_LAYER3_BASE_PROMPT")
        if not prompt:
            config_path = os.getenv("LLM_LAYER3_PROMPT_CONFIG")
            if config_path and os.path.exists(config_path):
                with open(config_path, "r") as f:
                    prompt = f.read()
        return prompt or "You are a helpful AI assistant."

    async def generate(self, prompt: str, context: Optional[dict] = None) -> str:
        """Mocked generation"""
        return f"Response to: {prompt[:50]}..."
