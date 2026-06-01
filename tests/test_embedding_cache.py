import tempfile
import time
from pathlib import Path

import pytest

from ragcore.embeddings.cache import DiskCache, EmbeddingCache, LRUCache


class TestLRUCache:
    def test_set_get(self):
        cache = LRUCache(maxsize=10)
        cache.set("key1", [0.1, 0.2])
        assert cache.get("key1") == [0.1, 0.2]

    def test_get_miss(self):
        cache = LRUCache(maxsize=10)
        assert cache.get("nonexistent") is None

    def test_eviction(self):
        cache = LRUCache(maxsize=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_lru_reorder(self):
        cache = LRUCache(maxsize=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")
        cache.set("c", 3)
        assert cache.get("b") is None
        assert cache.get("a") == 1

    def test_clear(self):
        cache = LRUCache(maxsize=10)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.size == 0

    def test_size(self):
        cache = LRUCache(maxsize=10)
        assert cache.size == 0
        cache.set("a", 1)
        assert cache.size == 1


class TestDiskCache:
    @pytest.fixture
    def db_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    def test_set_get(self, db_path):
        cache = DiskCache(db_path=db_path, ttl=3600)
        cache.set("key1", {"value": [0.1, 0.2]})
        result = cache.get("key1")
        assert result == {"value": [0.1, 0.2]}

    def test_get_miss(self, db_path):
        cache = DiskCache(db_path=db_path, ttl=3600)
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self, db_path):
        cache = DiskCache(db_path=db_path, ttl=0.1)
        cache.set("key1", [0.1])
        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_clear(self, db_path):
        cache = DiskCache(db_path=db_path, ttl=3600)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None

    def test_close(self, db_path):
        cache = DiskCache(db_path=db_path, ttl=3600)
        cache.set("a", 1)
        cache.close()
        assert cache.get("a") == 1


class TestEmbeddingCache:
    @pytest.fixture
    def cache(self):
        return EmbeddingCache()

    def test_set_get(self, cache):
        cache.set("key1", [0.1, 0.2, 0.3])
        assert cache.get("key1") == [0.1, 0.2, 0.3]

    def test_get_miss(self, cache):
        assert cache.get("nonexistent") is None

    def test_clear(self, cache):
        cache.set("a", [1.0])
        cache.set("b", [2.0])
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_make_key(self):
        key = EmbeddingCache.make_key("q", "hello", "model")
        assert key == "q:hello:model"

    def test_memory_size(self, cache):
        assert cache.memory_size == 0
        cache.set("a", [1.0])
        assert cache.memory_size == 1
