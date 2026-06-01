from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ragcore.core.config import settings
from ragcore.embeddings.provider import EmbeddingProvider
from ragcore.vectorstore.faiss_store import FAISSVectorStore


class BaseRetriever(ABC):
    def __init__(
        self,
        vectorstore: FAISSVectorStore,
        embedding_provider: EmbeddingProvider,
        config: dict[str, Any] | None = None,
    ):
        self._vectorstore = vectorstore
        self._embedding_provider = embedding_provider
        self.config = config or {}
        self.top_k = self.config.get("top_k", settings.retrieval_top_k)
        self.score_threshold = self.config.get("score_threshold", settings.retrieval_score_threshold)

    @abstractmethod
    def retrieve(self, query: str, k: int | None = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def retrieve_with_embeddings(
        self, query_emb: list[float], k: int | None = None
    ) -> list[dict[str, Any]]:
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("Retriever", "").lower()
