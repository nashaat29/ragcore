from __future__ import annotations

from typing import Any

from ragcore.core.logger import get_logger
from ragcore.retrieval.base import BaseRetriever

logger = get_logger("ragcore.retrieval.simple")


class SimpleRetriever(BaseRetriever):
    def retrieve(self, query: str, k: int | None = None) -> list[dict[str, Any]]:
        k = k or self.top_k
        results = self._vectorstore.similarity_search(
            query, k=k, score_threshold=self.score_threshold if self.score_threshold > 0 else None
        )
        logger.debug(f"Simple retriever: {len(results)} results for query (k={k})")
        return results

    def retrieve_with_embeddings(
        self, query_emb: list[float], k: int | None = None
    ) -> list[dict[str, Any]]:
        k = k or self.top_k
        results = self._vectorstore.similarity_search_with_embedding(
            query_emb, k=k, score_threshold=self.score_threshold if self.score_threshold > 0 else None
        )
        return results
