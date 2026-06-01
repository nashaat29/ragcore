from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessageChunk
from langchain_ollama import ChatOllama

from ragcore.core.config import settings
from ragcore.core.exceptions import LLMError, LLMTimeoutError
from ragcore.core.logger import get_logger

logger = get_logger("ragcore.llm.provider")


class LLMProvider:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.model_name = self.config.get("model", settings.llm_model)
        self.base_url = self.config.get("base_url", settings.llm_base_url)
        self.temperature = self.config.get("temperature", settings.llm_temperature)
        self.max_tokens = self.config.get("max_tokens", settings.llm_max_tokens)
        self.timeout = self.config.get("timeout", settings.llm_timeout)

        self._client: ChatOllama | None = None
        self._streaming_client: ChatOllama | None = None

    @property
    def client(self) -> ChatOllama:
        if self._client is None:
            self._client = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=self.temperature,
                num_predict=self.max_tokens,
                timeout=self.timeout,
            )
        return self._client

    @property
    def streaming_client(self) -> ChatOllama:
        if self._streaming_client is None:
            self._streaming_client = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=self.temperature,
                num_predict=self.max_tokens,
                timeout=self.timeout,
                streaming=True,
            )
        return self._streaming_client

    def invoke(self, prompt: str) -> str:
        try:
            response = self.client.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg:
                raise LLMTimeoutError(f"LLM request timed out after {self.timeout}s: {e}") from e
            raise LLMError(f"LLM invocation failed: {e}") from e

    async def invoke_async(self, prompt: str) -> str:
        import asyncio

        try:
            return await asyncio.to_thread(self.invoke, prompt)
        except Exception as e:
            raise LLMError(f"Async LLM invocation failed: {e}") from e

    def stream(self, prompt: str) -> AsyncIterator[str]:
        async def _stream() -> AsyncIterator[str]:
            try:
                async for chunk in self.streaming_client.astream(prompt):
                    if isinstance(chunk, AIMessageChunk):
                        content = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if content:
                            yield content
                    elif hasattr(chunk, "content"):
                        if chunk.content:
                            yield chunk.content
                    else:
                        yield str(chunk)
            except Exception as e:
                raise LLMError(f"LLM streaming failed: {e}") from e

        return _stream()

    def get_token_count(self, text: str) -> int:
        return len(text) // 4
