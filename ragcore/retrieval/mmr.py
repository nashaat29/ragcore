from __future__ import annotations

from typing import Any

from ragcore.core.logger import get_logger
from ragcore.retrieval.base import BaseRetriever

logger = get_logger("ragcore.retrieval.mmr")


class MMRRetriever(BaseRetriever):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lambda_mult = self.config.get("lambda_mult", 0.5)
        self.k_initial = self.config.get("k_initial", self.top_k * 5)

    def retrieve(self, query: str, k: int | None = None) -> list[dict[str, Any]]:
        k = k or self.top_k
        results = self._vectorstore.max_marginal_relevance_search(
            query,
            k=k,
            lambda_mult=self.lambda_mult,
            k_initial=self.k_initial,
        )
        if self.score_threshold > 0:
            results = [r for r in results if r.get("score", 1.0) >= self.score_threshold]
        logger.debug(f"MMR retriever: {len(results)} results (lambda={self.lambda_mult}, k={k})")
        return results

    def retrieve_with_embeddings(
        self, query_emb: list[float], k: int | None = None
    ) -> list[dict[str, Any]]:
        k = k or self.top_k
        results = self._vectorstore.similarity_search_with_embedding(
            query_emb,
            k=k,
            score_threshold=self.score_threshold if self.score_threshold > 0 else None,
        )
        return results
