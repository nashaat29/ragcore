import tempfile
from pathlib import Path

import pytest

from ragcore.vectorstore.faiss_store import FAISSVectorStore


class MockEmbeddingProvider:
    dimension = 4

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3, 0.4]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


@pytest.fixture
def store():
    return FAISSVectorStore(embedding_provider=MockEmbeddingProvider())


class TestFAISSVectorStore:
    def test_init(self, store):
        assert store.dimension == 4
        assert store.size == 0

    def test_add_texts(self, store):
        ids = store.add_texts(["hello world", "test document"])
        assert len(ids) == 2
        assert store.size == 2

    def test_add_texts_empty(self, store):
        ids = store.add_texts([])
        assert ids == []

    def test_similarity_search(self, store):
        store.add_texts(["hello world", "test document"])
        results = store.similarity_search("hello", k=2)
        assert len(results) == 2
        assert "text" in results[0]
        assert "score" in results[0]

    def test_similarity_search_empty(self, store):
        results = store.similarity_search("hello")
        assert results == []

    def test_similarity_search_with_embedding(self, store):
        store.add_texts(["hello world"])
        results = store.similarity_search_with_embedding([0.1, 0.2, 0.3, 0.4], k=1)
        assert len(results) == 1

    def test_delete(self, store):
        ids = store.add_texts(["a", "b", "c"])
        assert store.size == 3
        deleted = store.delete([ids[0]])
        assert deleted == 1
        assert store.size == 2

    def test_delete_nonexistent(self, store):
        store.add_texts(["a"])
        deleted = store.delete(["nonexistent"])
        assert deleted == 0

    def test_clear(self, store):
        store.add_texts(["a", "b"])
        store.clear()
        assert store.size == 0

    def test_documents_property(self, store):
        store.add_texts(["hello"], [{"source": "test"}])
        docs = store.documents
        assert len(docs) == 1
        assert docs[0]["text"] == "hello"

    def test_get_stats(self, store):
        store.add_texts(["hello"])
        stats = store.get_stats()
        assert stats["total_vectors"] == 1
        assert stats["dimension"] == 4

    def test_save_and_load(self, store):
        store.add_texts(["hello world", "test document"])
        with tempfile.TemporaryDirectory() as tmpdir:
            store.save(tmpdir)
            assert (Path(tmpdir) / "index.faiss").exists()
            assert (Path(tmpdir) / "metadata.json").exists()

            new_store = FAISSVectorStore(embedding_provider=MockEmbeddingProvider())
            new_store.load(tmpdir)
            assert new_store.size == 2
            assert new_store.dimension == 4

    def test_save_and_load_no_metadata_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(Exception):
                store = FAISSVectorStore(embedding_provider=MockEmbeddingProvider())
                store.load(tmpdir)

    def test_mmr_search(self, store):
        store.add_texts(["hello world", "test document", "foo bar"])
        results = store.max_marginal_relevance_search("hello", k=2)
        assert len(results) <= 2

    def test_mmr_search_empty(self, store):
        results = store.max_marginal_relevance_search("hello")
        assert results == []

    def test_documents_snapshot_independence(self, store):
        store.add_texts(["hello"])
        docs = store.documents
        docs.append({"text": "injected"})
        assert len(store.documents) == 1
