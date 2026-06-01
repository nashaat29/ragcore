from __future__ import annotations

import re
from typing import Any

from rank_bm25 import BM25Okapi

from ragcore.core.logger import get_logger
from ragcore.retrieval.base import BaseRetriever

logger = get_logger("ragcore.retrieval.hybrid")


class HybridRetriever(BaseRetriever):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.alpha = self.config.get("alpha", 0.5)
        self._bm25: BM25Okapi | None = None
        self._bm25_corpus: list[str] = []
        self._corpus_initialized = False

    def _ensure_bm25(self) -> None:
        if self._corpus_initialized:
            return
        all_texts = [doc.get("text", "") for doc in self._vectorstore.documents]
        if not all_texts:
            self._bm25 = BM25Okapi(corpus=[""])
            self._corpus_initialized = True
            return
        tokenized = [self._tokenize(t) for t in all_texts]
        self._bm25 = BM25Okapi(corpus=tokenized)
        self._bm25_corpus = all_texts
        self._corpus_initialized = True

    def _rebuild_bm25(self) -> None:
        self._corpus_initialized = False
        self._ensure_bm25()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def retrieve(self, query: str, k: int | None = None) -> list[dict[str, Any]]:
        k = k or self.top_k
        self._ensure_bm25()

        dense_results = self._vectorstore.similarity_search(
            query, k=max(k * 2, 10), score_threshold=None
        )

        tokenized_query = self._tokenize(query)
        bm25_scores = self._bm25.get_scores(tokenized_query)

        dense_map: dict[int, float] = {}
        for r in dense_results:
            idx = r.get("index")
            if idx is not None:
                dense_map[int(idx)] = r.get("score", 0.0)

        all_scores: list[tuple[int, float, float]] = []
        for idx in range(len(self._vectorstore.documents)):
            dense_score = dense_map.get(idx, 0.0)
            sparse_score = float(bm25_scores[idx]) if idx < len(bm25_scores) else 0.0

            dense_norm = self._min_max_normalize(dense_score, list(dense_map.values()))
            sparse_norm = self._min_max_normalize(sparse_score, bm25_scores.tolist())

            combined = self.alpha * dense_norm + (1 - self.alpha) * sparse_norm
            all_scores.append((idx, combined, dense_score))

        all_scores.sort(key=lambda x: x[1], reverse=True)
        top_results = all_scores[:k]

        results: list[dict[str, Any]] = []
        for idx, combined, dense_score in top_results:
            doc = dict(self._vectorstore.documents[idx])
            doc["score"] = float(combined)
            doc["dense_score"] = float(dense_score)
            doc["sparse_score"] = float(bm25_scores[idx]) if idx < len(bm25_scores) else 0.0
            doc["index"] = idx
            if self.score_threshold <= 0 or combined >= self.score_threshold:
                results.append(doc)

        logger.debug(f"Hybrid retriever: {len(results)} results (alpha={self.alpha}, k={k})")
        return results

    def retrieve_with_embeddings(
        self, query_emb: list[float], k: int | None = None
    ) -> list[dict[str, Any]]:
        k = k or self.top_k
        self._ensure_bm25()

        dense_results = self._vectorstore.similarity_search_with_embedding(
            query_emb, k=max(k * 2, 10), score_threshold=None
        )

        dense_map: dict[int, float] = {}
        for r in dense_results:
            idx = r.get("index")
            if idx is not None:
                dense_map[int(idx)] = r.get("score", 0.0)

        all_scores: list[tuple[int, float, float]] = []
        for idx in range(len(self._vectorstore.documents)):
            dense_score = dense_map.get(idx, 0.0)

            if dense_map:
                dense_norm = self._min_max_normalize(dense_score, list(dense_map.values()))
            else:
                dense_norm = 0.0

            combined = dense_norm
            all_scores.append((idx, combined, dense_score))

        all_scores.sort(key=lambda x: x[1], reverse=True)
        top_results = all_scores[:k]

        results: list[dict[str, Any]] = []
        for idx, combined, dense_score in top_results:
            doc = dict(self._vectorstore.documents[idx])
            doc["score"] = float(combined)
            doc["dense_score"] = float(dense_score)
            doc["sparse_score"] = 0.0
            doc["index"] = idx
            if self.score_threshold <= 0 or combined >= self.score_threshold:
                results.append(doc)

        logger.debug(f"Hybrid retriever (embeddings-only): {len(results)} results (k={k})")
        return results

    @staticmethod
    def _min_max_normalize(value: float, values: list[float]) -> float:
        if not values:
            return 0.0
        min_v, max_v = min(values), max(values)
        if max_v - min_v == 0:
            return 0.0
        return (value - min_v) / (max_v - min_v)
