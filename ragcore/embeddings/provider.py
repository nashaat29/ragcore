from __future__ import annotations

import threading
from typing import Any

from langchain_ollama import OllamaEmbeddings

from ragcore.core.config import settings
from ragcore.core.exceptions import EmbeddingError
from ragcore.core.logger import get_logger
from ragcore.embeddings.cache import EmbeddingCache

logger = get_logger("ragcore.embeddings.provider")


class EmbeddingProvider:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.model_name = self.config.get("model", settings.embedding_model)
        self.base_url = self.config.get("base_url", settings.embedding_base_url)
        self._client: OllamaEmbeddings | None = None
        self._lock = threading.Lock()
        self._cache = EmbeddingCache() if settings.cache_enabled else None
        self._dimension: int | None = None

    @property
    def client(self) -> OllamaEmbeddings:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = OllamaEmbeddings(
                        model=self.model_name,
                        base_url=self.base_url,
                    )
        return self._client

    def embed_query(self, text: str) -> list[float]:
        cache_key = f"q:{text}:{self.model_name}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            result = self.client.embed_query(text)
            if self._cache:
                self._cache.set(cache_key, result)
            return result
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        uncached: list[tuple[int, str]] = []
        results: list[list[float] | None] = [None] * len(texts)

        if self._cache:
            for i, text in enumerate(texts):
                cache_key = f"d:{text}:{self.model_name}"
                cached = self._cache.get(cache_key)
                if cached is not None:
                    results[i] = cached
                else:
                    uncached.append((i, text))
        else:
            uncached = list(enumerate(texts))

        if uncached:
            uncached_texts = [t for _, t in uncached]
            try:
                batch_result = self.client.embed_documents(uncached_texts)
                for (idx, text), emb in zip(uncached, batch_result):
                    results[idx] = emb
                    if self._cache:
                        self._cache.set(f"d:{text}:{self.model_name}", emb)
            except Exception as e:
                raise EmbeddingError(f"Failed to embed documents: {e}") from e

        return [r for r in results if r is not None]

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            sample = self.embed_query("dimension probe")
            self._dimension = len(sample)
        return self._dimension
