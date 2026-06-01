from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from ragcore.core.exceptions import VectorStoreError
from ragcore.core.logger import get_logger
from ragcore.embeddings.provider import EmbeddingProvider

logger = get_logger("ragcore.vectorstore.faiss_store")


class FAISSVectorStore:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        dimension: int | None = None,
        index_path: str | Path | None = None,
    ):
        self._embedding_provider = embedding_provider
        self._dimension = dimension or embedding_provider.dimension
        self._index_path = Path(index_path) if index_path else None

        self._index: faiss.Index = self._build_index()
        self._documents: list[dict[str, Any]] = []
        self._doc_id_to_idx: dict[str, int] = {}
        self._lock = threading.RLock()

    def _build_index(self) -> faiss.Index:
        index = faiss.IndexFlatIP(self._dimension)
        return index

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def size(self) -> int:
        return self._index.ntotal

    @property
    def documents(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._documents)

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        if not texts:
            return []

        embeddings = self._embedding_provider.embed_documents(texts)
        embedding_array = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(embedding_array)

        with self._lock:
            start_idx = self._index.ntotal
            self._index.add(embedding_array)

            doc_ids: list[str] = []
            for i, text in enumerate(texts):
                doc_id = ids[i] if ids and i < len(ids) else f"doc_{start_idx + i}"
                metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                metadata["text"] = text
                metadata["doc_id"] = doc_id

                idx_in_store = start_idx + i
                self._documents.append(metadata)
                self._doc_id_to_idx[doc_id] = idx_in_store
                doc_ids.append(doc_id)

        logger.info(f"Added {len(texts)} texts to FAISS index (total: {self._index.ntotal})")
        return doc_ids

    def similarity_search(
        self, query: str, k: int = 4, score_threshold: float | None = None
    ) -> list[dict[str, Any]]:
        query_emb = self._embedding_provider.embed_query(query)
        query_array = np.array([query_emb], dtype=np.float32)
        faiss.normalize_L2(query_array)

        with self._lock:
            actual_k = min(k, self._index.ntotal)
            if actual_k == 0:
                return []

            scores, indices = self._index.search(query_array, actual_k)

            results: list[dict[str, Any]] = []
            for score, idx in zip(scores[0], indices[0]):
                if score_threshold is not None and score < score_threshold:
                    continue
                doc = dict(self._documents[idx])
                doc["score"] = float(score)
                doc["index"] = int(idx)
                results.append(doc)

        return results

    def similarity_search_with_embedding(
        self, query_emb: list[float], k: int = 4, score_threshold: float | None = None
    ) -> list[dict[str, Any]]:
        query_array = np.array([query_emb], dtype=np.float32)
        faiss.normalize_L2(query_array)

        with self._lock:
            actual_k = min(k, self._index.ntotal)
            if actual_k == 0:
                return []

            scores, indices = self._index.search(query_array, actual_k)

            results: list[dict[str, Any]] = []
            for score, idx in zip(scores[0], indices[0]):
                if score_threshold is not None and score < score_threshold:
                    continue
                doc = dict(self._documents[idx])
                doc["score"] = float(score)
                doc["index"] = int(idx)
                results.append(doc)

        return results

    def max_marginal_relevance_search(
        self, query: str, k: int = 4, lambda_mult: float = 0.5, k_initial: int | None = None
    ) -> list[dict[str, Any]]:
        fetch_k = k_initial or k * 5
        query_emb = self._embedding_provider.embed_query(query)
        query_array = np.array([query_emb], dtype=np.float32)
        faiss.normalize_L2(query_array)

        with self._lock:
            actual_fetch = min(fetch_k, self._index.ntotal)
            if actual_fetch == 0:
                return []

            scores, indices = self._index.search(query_array, actual_fetch)

            candidate_texts: list[str] = []
            candidate_docs: list[dict[str, Any]] = []
            for idx in indices[0]:
                doc = dict(self._documents[idx])
                candidate_docs.append(doc)
                candidate_texts.append(doc.get("text", ""))

            candidate_embeddings = np.array(
                [self._embedding_provider.embed_query(text) for text in candidate_texts],
                dtype=np.float32,
            )
            faiss.normalize_L2(candidate_embeddings)

        selected = self._mmr_selection(
            query_emb=np.array(query_emb, dtype=np.float32),
            candidate_embeddings=candidate_embeddings,
            indices=np.array(range(len(candidate_docs))),
            scores=scores[0],
            k=k,
            lambda_mult=lambda_mult,
        )

        return [
            {
                **candidate_docs[idx],
                "score": float(score),
                "index": int(idx),
            }
            for idx, score in selected
        ]

    @staticmethod
    def _mmr_selection(
        query_emb: np.ndarray,
        candidate_embeddings: np.ndarray,
        indices: np.ndarray,
        scores: np.ndarray,
        k: int,
        lambda_mult: float,
    ) -> list[tuple[int, float]]:
        selected: list[int] = []
        selected_embeddings: list[np.ndarray] = []
        results: list[tuple[int, float]] = []

        for _ in range(min(k, len(indices))):
            best_score = -1.0
            best_idx = -1
            best_full_idx = -1

            for i in range(len(indices)):
                if i in selected:
                    continue

                relevance = float(scores[i])
                if selected_embeddings:
                    sim_to_selected = max(
                        float(np.dot(candidate_embeddings[i], s))
                        for s in selected_embeddings
                    )
                    mmr_score = lambda_mult * relevance - (1 - lambda_mult) * sim_to_selected
                else:
                    mmr_score = relevance

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
                    best_full_idx = int(indices[i])

            if best_idx >= 0:
                selected.append(best_idx)
                selected_embeddings.append(candidate_embeddings[best_idx])
                results.append((best_full_idx, float(scores[best_idx])))

        return results

    def delete(self, doc_ids: list[str]) -> int:
        with self._lock:
            if not self._index.ntotal:
                return 0

            indices_to_remove = sorted(
                (self._doc_id_to_idx.get(did) for did in doc_ids if did in self._doc_id_to_idx),
                reverse=True,
            )
            if not indices_to_remove:
                return 0

            keep_mask = np.ones(self._index.ntotal, dtype=bool)
            for idx in indices_to_remove:
                keep_mask[idx] = False

            self._reindex_with_mask(keep_mask)

            for did in doc_ids:
                self._doc_id_to_idx.pop(did, None)

        logger.info(f"Deleted {len(indices_to_remove)} documents from FAISS index")
        return len(indices_to_remove)

    def _reindex_with_mask(self, keep_mask: np.ndarray) -> None:
        old_vectors = np.zeros((self._index.ntotal, self._dimension), dtype=np.float32)
        for i in range(self._index.ntotal):
            old_vectors[i] = self._index.reconstruct(i)

        kept_vectors = old_vectors[keep_mask]
        kept_documents = [doc for i, doc in enumerate(self._documents) if keep_mask[i]]

        new_index = self._build_index()
        if len(kept_vectors) > 0:
            new_index.add(kept_vectors)

        self._index = new_index
        self._documents = kept_documents
        self._doc_id_to_idx = {
            doc["doc_id"]: i for i, doc in enumerate(kept_documents) if "doc_id" in doc
        }

    def clear(self) -> None:
        with self._lock:
            self._index = self._build_index()
            self._documents.clear()
            self._doc_id_to_idx.clear()
        logger.info("FAISS index cleared")

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_vectors": self._index.ntotal,
                "dimension": self._dimension,
                "total_documents": len(self._documents),
                "index_type": type(self._index).__name__,
            }

    def save(self, directory: str | Path) -> None:
        save_dir = Path(directory)
        save_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            faiss.write_index(self._index, str(save_dir / "index.faiss"))

            metadata = {
                "documents": list(self._documents),
                "doc_id_to_idx": dict(self._doc_id_to_idx),
                "dimension": self._dimension,
            }

        with open(save_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, default=str)

        logger.info(f"FAISS index saved to {save_dir}")

    def load(self, directory: str | Path) -> None:
        load_dir = Path(directory)
        index_file = load_dir / "index.faiss"
        metadata_json = load_dir / "metadata.json"

        if not index_file.exists():
            raise VectorStoreError(f"Index file not found: {index_file}")

        new_index = faiss.read_index(str(index_file))

        if metadata_json.exists():
            with open(metadata_json) as f:
                metadata = json.load(f)
        else:
            raise VectorStoreError(f"Metadata file not found: expected {metadata_json}")

        with self._lock:
            self._index = new_index
            self._documents = metadata["documents"]
            self._doc_id_to_idx = metadata["doc_id_to_idx"]
            self._dimension = metadata["dimension"]

        logger.info(f"FAISS index loaded from {load_dir} ({self._index.ntotal} vectors)")
