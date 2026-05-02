"""LLM Provider Interface - Phase 3.

Replaces the fake simulation with a real provider abstraction supporting
OpenAI, Anthropic, and Gemini. Set LLM_PROVIDER env var to switch.

Usage:
    export LLM_PROVIDER=openai      # OpenAI GPT-4
    export LLM_PROVIDER=anthropic   # Anthropic Claude
    export LLM_PROVIDER=gemini      # Google Gemini
    export LLM_PROVIDER=mock        # Development/fallback (no API key needed)
"""
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional

import httpx


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    source: str = "llm"


class BaseLLMProvider(ABC):
    """Abstract LLM provider — implement parse() for a new backend."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        context: Optional[dict] = None,
        sources: Optional[List[str]] = None,
    ) -> LLMResponse:
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    """Development-only mock — returns canned responses, no API key needed."""

    async def generate(
        self,
        prompt: str,
        context: Optional[dict] = None,
        sources: Optional[List[str]] = None,
    ) -> LLMResponse:
        import asyncio
        await asyncio.sleep(0.05)  # Simulate network latency

        state_str = (context or {}).get("state", "IDLE")
        if sources:
            best = sources[0][:200]
            content = (
                f"根據目前的對話狀態 ({state_str}) 與知識庫資料，關於 '{prompt}'：\n\n"
                f"{best}...\n\n"
                f"這是一個由大型語言模型生成的整合性回答。"
            )
        else:
            content = (
                f"關於您詢問的 '{prompt}'，"
                f"雖然目前的知識庫中沒有直接匹配的規則，但根據我的理解：\n\n"
                f"這是一個針對您問題的通用生成回答，目前的對話階段為 {state_str}。"
            )

        return LLMResponse(
            content=content,
            model="mock",
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(content.split()),
            total_tokens=len(prompt.split()) + len(content.split()),
        )


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT-4 / GPT-3.5-turbo provider."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = "https://api.openai.com/v1"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        context: Optional[dict] = None,
        sources: Optional[List[str]] = None,
    ) -> LLMResponse:
        if sources:
            context_block = "\n".join(f"- {s}" for s in sources[:3])
            system_prompt = (
                f"你是一個客服助手。請根據以下參考資料回答用戶問題。\n"
                f"參考資料：\n{context_block}"
            )
        else:
            system_prompt = "你是一個客服助手。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        client = await self._get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.3,
        }

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["content"],
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

    async def close(self):
        if self._client:
            await self._client.aclose()


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = "https://api.anthropic.com/v1"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        context: Optional[dict] = None,
        sources: Optional[List[str]] = None,
    ) -> LLMResponse:
        if sources:
            context_block = "\n".join(f"- {s}" for s in sources[:3])
            system = (
                f"你是一個客服助手。請根據以下參考資料回答用戶問題。\n"
                f"參考資料：\n{context_block}"
            )
        else:
            system = "你是一個客服助手。"

        messages = [{"role": "user", "content": prompt}]

        client = await self._get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "system": system,
            "max_tokens": 500,
        }

        response = await client.post("/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["content"][0]["text"],
            model=self.model,
            prompt_tokens=data.get("usage", {}).get("input_tokens", 0),
            completion_tokens=data.get("usage", {}).get("output_tokens", 0),
            total_tokens=(
                data.get("usage", {}).get("input_tokens", 0)
                + data.get("usage", {}).get("output_tokens", 0)
            ),
        )

    async def close(self):
        if self._client:
            await self._client.aclose()


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider via AIStudio REST API."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"https://generativelanguage.googleapis.com/v1beta/models",
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        context: Optional[dict] = None,
        sources: Optional[List[str]] = None,
    ) -> LLMResponse:
        if sources:
            context_block = "\n".join(f"- {s}" for s in sources[:3])
            prompt = (
                f"根據以下參考資料回答用戶問題。\n"
                f"參考資料：\n{context_block}\n\n"
                f"用戶問題：{prompt}"
            )

        client = await self._get_client()
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 500, "temperature": 0.3},
        }

        url = f"/{self.model}:generateContent?key={self.api_key}"
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["candidates"][0]["content"]["parts"][0]["text"]

        return LLMResponse(
            content=content,
            model=self.model,
            prompt_tokens=data.get("usageMetadata", {}).get("promptTokenCount", 0),
            completion_tokens=data.get("usageMetadata", {}).get("candidatesTokenCount", 0),
            total_tokens=data.get("usageMetadata", {}).get("totalTokenCount", 0),
        )

    async def close(self):
        if self._client:
            await self._client.aclose()


def get_llm_provider() -> BaseLLMProvider:
    """Factory: return LLM provider based on LLM_PROVIDER env var.

    Env vars per provider:
      OPENAI:     OPENAI_API_KEY, OPENAI_MODEL
      ANTHROPIC:  ANTHROPIC_API_KEY, ANTHROPIC_MODEL
      GEMINI:     GEMINI_API_KEY, GEMINI_MODEL
      MOCK:       (none required)
    """
    provider = os.getenv("LLM_PROVIDER", "mock").lower()

    if provider == "openai":
        return OpenAIProvider()
    elif provider == "anthropic":
        return AnthropicProvider()
    elif provider == "gemini":
        return GeminiProvider()
    else:
        return MockLLMProvider()
