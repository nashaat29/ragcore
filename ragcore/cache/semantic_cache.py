from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from ragcore.core.config import settings
from ragcore.core.logger import get_logger
from ragcore.embeddings.provider import EmbeddingProvider

logger = get_logger("ragcore.cache.semantic_cache")


class SemanticCache:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        db_path: str | Path | None = None,
        similarity_threshold: float | None = None,
        ttl: int | None = None,
    ):
        self._embedding_provider = embedding_provider or EmbeddingProvider()
        self._similarity_threshold = similarity_threshold or settings.cache_semantic_threshold
        self._ttl = ttl or settings.cache_semantic_ttl
        self._db_path = Path(db_path or str(settings.cache_path / "semantic_cache.db"))
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path), timeout=5, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    response TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    last_accessed REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_query_hash ON semantic_cache(query_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created_at ON semantic_cache(created_at)"
            )
            conn.commit()

    def get(self, query: str) -> dict[str, Any] | None:
        query_emb = self._embedding_provider.embed_query(query)
        query_array = np.array(query_emb, dtype=np.float32)

        with self._lock:
            conn = self._get_conn()
            now = time.time()
            rows = conn.execute(
                """
                SELECT id, query_text, embedding, response, metadata, created_at, access_count
                FROM semantic_cache
                WHERE (? - created_at) < ?
                ORDER BY access_count DESC, last_accessed DESC
                LIMIT 50
                """,
                (now, self._ttl),
            ).fetchall()

            best_similarity = -1.0
            best_result: dict[str, Any] | None = None
            best_cache_id = None

            for row in rows:
                cache_id, cached_query, emb_blob, response_json, meta_json, created_at, access_count = row
                cached_emb = np.frombuffer(emb_blob, dtype=np.float32)

                cached_norm = cached_emb / (np.linalg.norm(cached_emb) + 1e-10)
                query_norm = query_array / (np.linalg.norm(query_array) + 1e-10)
                similarity = float(np.dot(cached_norm, query_norm))

                if similarity > best_similarity:
                    best_similarity = similarity
                    if similarity >= self._similarity_threshold:
                        try:
                            full_result = json.loads(response_json)
                        except (json.JSONDecodeError, TypeError):
                            full_result = {"answer": response_json}
                        full_result["cached_query"] = cached_query
                        full_result["similarity"] = similarity
                        full_result["cached_at"] = created_at
                        best_result = full_result
                        best_cache_id = cache_id

            if best_result and best_cache_id is not None:
                conn.execute(
                    "UPDATE semantic_cache SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    (now, best_cache_id),
                )
                conn.commit()
                logger.debug(f"Semantic cache hit (similarity={best_similarity:.4f})")
                return best_result

            logger.debug(f"Semantic cache miss (best_similarity={best_similarity:.4f})")
            return None

    def set(self, query: str, full_response: dict[str, Any]) -> None:
        query_emb = self._embedding_provider.embed_query(query)
        emb_blob = np.array(query_emb, dtype=np.float32).tobytes()

        with self._lock:
            conn = self._get_conn()
            now = time.time()
            conn.execute(
                """
                INSERT INTO semantic_cache (query_hash, query_text, embedding, response, metadata, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hashlib.sha256(query.encode()).hexdigest(),
                    query[:500],
                    emb_blob,
                    json.dumps(full_response, default=str),
                    json.dumps({
                        "sources_count": len(full_response.get("sources", [])),
                        "retrieval_strategy": full_response.get("retrieval_strategy", ""),
                    }),
                    now,
                    now,
                ),
            )
            conn.commit()
            logger.debug("Semantic cache entry added")

    def clear(self) -> int:
        with self._lock:
            conn = self._get_conn()
            count = conn.execute("SELECT COUNT(*) FROM semantic_cache").fetchone()[0]
            conn.execute("DELETE FROM semantic_cache")
            conn.commit()
            logger.info(f"Semantic cache cleared ({count} entries)")
            return count

    def stats(self) -> dict[str, Any]:
        with self._lock:
            conn = self._get_conn()
            total = conn.execute("SELECT COUNT(*) FROM semantic_cache").fetchone()[0]
            return {
                "total_entries": total,
                "threshold": self._similarity_threshold,
                "ttl": self._ttl,
                "db_path": str(self._db_path),
            }
