import os

import pytest


@pytest.fixture(autouse=True)
def setup_env():
    os.environ["TESTING"] = "true"
    os.environ["LLM_LAYER3_BASE_PROMPT"] = "You are a professional assistant."
    os.environ["LLM_MODEL_PROD"] = "gpt-4o"
    os.environ["LLM_LAYER3_PROMPT_CONFIG"] = "config/prompts/layer3.txt"
    if "SIMULATE_LLM" not in os.environ:
        os.environ["SIMULATE_LLM"] = "true"
