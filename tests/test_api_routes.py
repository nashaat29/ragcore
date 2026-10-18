import pytest
from fastapi.testclient import TestClient

from ragcore.api.server import create_app
from ragcore.pipeline.rag_pipeline import RAGPipeline


class MockVectorStore:
    def __init__(self):
        self._documents = []
        self._index = type("obj", (object,), {"ntotal": 0})()

    def add_texts(self, texts, metadatas=None, ids=None):
        n = len(texts)
        self._documents.extend([
            {"text": t, "doc_id": f"doc_{i}", **({"source": "test"} if metadatas else {})}
            for i, t in enumerate(texts)
        ])
        self._index.ntotal += n
        return [f"doc_{i}" for i in range(n)]

    def clear(self):
        self._documents.clear()
        self._index.ntotal = 0

    def get_stats(self):
        return {
            "total_vectors": self._index.ntotal,
            "dimension": 4,
            "total_documents": len(self._documents),
            "index_type": "MockIndex",
        }

    def load(self, directory):
        pass

    def similarity_search(self, query, k=4, score_threshold=None):
        results = []
        for i, doc in enumerate(self._documents[:k]):
            d = dict(doc)
            d["score"] = 0.9
            d["index"] = i
            results.append(d)
        return results

    @property
    def dimension(self):
        return 4

    @property
    def size(self):
        return self._index.ntotal

    def delete(self, doc_ids):
        self._documents = [d for d in self._documents if d.get("doc_id") not in doc_ids]
        self._index.ntotal = len(self._documents)
        return len(doc_ids)

    @property
    def documents(self):
        return list(self._documents)


class MockEmbeddingProvider:
    dimension = 4

    def embed_query(self, text):
        return [0.1, 0.2, 0.3, 0.4]

    def embed_documents(self, texts):
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


class MockLLMProvider:
    def invoke(self, prompt):
        return "Test answer."

    async def stream(self, prompt):
        yield "Test "
        yield "answer."

    def invoke_async(self, prompt):
        import asyncio
        return asyncio.to_thread(self.invoke, prompt)


class MockIndexManager:
    def list_indexes(self):
        return []

    def get_active_index_name(self):
        return "default"

    def save_index(self, name, vectorstore):
        pass

    def load_index(self, name, vectorstore):
        pass

    def delete_index(self, name):
        pass

    def load_active_index(self, vectorstore):
        return False


@pytest.fixture
def pipeline():
    return RAGPipeline(
        embedding_provider=MockEmbeddingProvider(),
        llm_provider=MockLLMProvider(),
        vectorstore=MockVectorStore(),
        config={
            "guardrails_output_moderation": False,
            "guardrails_grounding_check": False,
        },
    )


@pytest.fixture
def client(pipeline):
    app = create_app(pipeline=pipeline)
    return TestClient(app)


class TestHealthEndpoints:
    def test_health_live(self, client):
        resp = client.get("/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "alive")

    def test_health_ready(self, client):
        resp = client.get("/health/ready")
        assert resp.status_code == 200


class TestIngestEndpoints:
    def test_ingest_text(self, client):
        resp = client.post("/ingest/text", json={"text": "hello world"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["doc_ids"]) > 0

    def test_ingest_text_empty(self, client):
        resp = client.post("/ingest/text", json={"text": ""})
        assert resp.status_code == 422

    def test_ingest_text_too_long(self, client):
        resp = client.post("/ingest/text", json={"text": "x" * 200000})
        assert resp.status_code == 422

    def test_ingest_directory_outside_allowed(self, client):
        resp = client.post(
            "/ingest/directory?path=/etc/passwd&recursive=false",
        )
        assert resp.status_code == 403


class TestQueryEndpoints:
    def test_query(self, client, pipeline):
        pipeline.ingest_text("RAG stands for Retrieval-Augmented Generation.")
        resp = client.post("/query", json={"question": "What is RAG?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "sources" in data

    def test_query_empty_question(self, client):
        resp = client.post("/query", json={"question": ""})
        assert resp.status_code == 422

    def test_retrieve_only(self, client, pipeline):
        pipeline.ingest_text("Some content.")
        resp = client.post("/query/retrieve", json={"question": "content"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_query_stream(self, client, pipeline):
        pipeline.ingest_text("RAG stands for Retrieval-Augmented Generation.")
        resp = client.post(
            "/query/stream",
            json={"question": "What is RAG?"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200


class TestManageEndpoints:
    def test_index_stats(self, client):
        resp = client.get("/manage/index/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "vectorstore" in data

    def test_index_list(self, client):
        resp = client.get("/manage/index/list")
        assert resp.status_code == 200

    def test_set_retrieval_strategy(self, client):
        resp = client.post("/manage/retrieval/strategy?strategy=mmr")
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "mmr"

    def test_set_retrieval_strategy_invalid(self, client):
        resp = client.post("/manage/retrieval/strategy?strategy=invalid")
        assert resp.status_code == 200

    def test_clear_index(self, client, pipeline):
        pipeline.ingest_text("hello")
        resp = client.post("/manage/index/clear")
        assert resp.status_code == 200

    def test_config(self, client):
        resp = client.get("/manage/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_model" in data
