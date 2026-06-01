from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from ragcore.core.config import settings
from ragcore.core.logger import get_logger

logger = get_logger("ragcore.embeddings.cache")


class LRUCache:
    def __init__(self, maxsize: int = 4096):
        self._maxsize = maxsize
        self._cache: dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._cache:
                value = self._cache.pop(key)
                self._cache[key] = value
                return value
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.pop(key)
            elif len(self._cache) >= self._maxsize:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = value

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)


class DiskCache:
    def __init__(self, db_path: str | Path | None = None, ttl: int = 86400):
        self._db_path = Path(db_path or str(settings.cache_path / "embed_cache.db"))
        self._ttl = ttl
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
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    key_hash TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created_at ON embedding_cache(created_at)"
            )
            conn.commit()

    def get(self, key: str) -> dict | list | None:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT value, created_at FROM embedding_cache WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()
            if row is None:
                return None
            value_json, created_at = row
            if self._ttl > 0 and (time.time() - created_at) > self._ttl:
                conn.execute("DELETE FROM embedding_cache WHERE key_hash = ?", (key_hash,))
                conn.commit()
                return None
            return json.loads(value_json)

    def set(self, key: str, value: dict | list) -> None:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO embedding_cache (key_hash, value, created_at) VALUES (?, ?, ?)",
                (key_hash, json.dumps(value, default=str), time.time()),
            )
            conn.commit()

    def clear(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM embedding_cache")
            conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


class EmbeddingCache:
    def __init__(self):
        self._memory = LRUCache(maxsize=settings.cache_lru_maxsize)
        self._disk = DiskCache(ttl=settings.cache_embedding_ttl)

    def get(self, key: str) -> list[float] | None:
        cached = self._memory.get(key)
        if cached is not None:
            return cached
        cached = self._disk.get(key)
        if cached is not None:
            self._memory.set(key, cached)
            return cached
        return None

    def set(self, key: str, value: list[float]) -> None:
        self._memory.set(key, value)
        self._disk.set(key, value)

    def clear(self) -> None:
        self._memory.clear()
        self._disk.clear()

    @property
    def memory_size(self) -> int:
        return self._memory.size

    @staticmethod
    def make_key(prefix: str, text: str, model: str) -> str:
        return f"{prefix}:{text}:{model}"
