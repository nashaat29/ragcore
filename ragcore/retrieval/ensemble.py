from __future__ import annotations

from typing import Any

from ragcore.core.logger import get_logger
from ragcore.retrieval.base import BaseRetriever
from ragcore.retrieval.hybrid import HybridRetriever
from ragcore.retrieval.mmr import MMRRetriever
from ragcore.retrieval.simple import SimpleRetriever

logger = get_logger("ragcore.retrieval.ensemble")

RETRIEVER_MAP: dict[str, type[BaseRetriever]] = {
    "simple": SimpleRetriever,
    "mmr": MMRRetriever,
    "hybrid": HybridRetriever,
}


class EnsembleRetriever(BaseRetriever):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.weights: dict[str, float] = self.config.get("weights", {
            "simple": 0.3,
            "mmr": 0.2,
            "hybrid": 0.5,
        })
        self._retrievers: dict[str, BaseRetriever] = {}

    def _get_retriever(self, name: str) -> BaseRetriever:
        if name not in self._retrievers:
            retriever_cls = RETRIEVER_MAP.get(name)
            if retriever_cls is None:
                raise ValueError(f"Unknown retriever: {name}")
            self._retrievers[name] = retriever_cls(
                vectorstore=self._vectorstore,
                embedding_provider=self._embedding_provider,
                config=self.config.get(f"{name}_config", {}),
            )
        return self._retrievers[name]

    def retrieve(self, query: str, k: int | None = None) -> list[dict[str, Any]]:
        k = k or self.top_k
        all_results: dict[int, dict[str, Any]] = {}

        for name, weight in self.weights.items():
            retriever = self._get_retriever(name)
            try:
                results = retriever.retrieve(query, k=k * 2)
                for r in results:
                    idx = r.get("index")
                    if idx is None:
                        continue
                    if idx not in all_results:
                        all_results[idx] = dict(r)
                        all_results[idx]["ensemble_score"] = 0.0
                        all_results[idx]["contributors"] = []
                    all_results[idx]["ensemble_score"] += weight * r.get("score", 0.5)
                    all_results[idx]["contributors"].append(name)
            except Exception as e:
                logger.warning(f"Ensemble retriever '{name}' failed: {e}")

        ranked = sorted(all_results.values(), key=lambda x: x.get("ensemble_score", 0), reverse=True)

        if self.score_threshold > 0:
            ranked = [r for r in ranked if r.get("ensemble_score", 0) >= self.score_threshold]

        top_k = ranked[:k]
        logger.debug(
            f"Ensemble retriever: {len(all_results)} combined -> {len(top_k)} results "
            f"(weights={self.weights})"
        )
        return top_k

    def retrieve_with_embeddings(
        self, query_emb: list[float], k: int | None = None
    ) -> list[dict[str, Any]]:
        k = k or self.top_k
        all_results: dict[int, dict[str, Any]] = {}

        for name, weight in self.weights.items():
            retriever = self._get_retriever(name)
            try:
                results = retriever.retrieve_with_embeddings(query_emb, k=k * 2)
                for r in results:
                    idx = r.get("index")
                    if idx is None:
                        continue
                    if idx not in all_results:
                        all_results[idx] = dict(r)
                        all_results[idx]["ensemble_score"] = 0.0
                        all_results[idx]["contributors"] = []
                    all_results[idx]["ensemble_score"] += weight * r.get("score", 0.5)
                    all_results[idx]["contributors"].append(name)
            except Exception as e:
                logger.warning(f"Ensemble retriever '{name}' failed: {e}")

        ranked = sorted(all_results.values(), key=lambda x: x.get("ensemble_score", 0), reverse=True)

        if self.score_threshold > 0:
            ranked = [r for r in ranked if r.get("ensemble_score", 0) >= self.score_threshold]

        top_k = ranked[:k]
        logger.debug(
            f"Ensemble retriever (embeddings): {len(all_results)} combined -> {len(top_k)} results "
            f"(weights={self.weights})"
        )
        return top_k
