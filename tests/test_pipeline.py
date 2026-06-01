import pytest

from ragcore.pipeline.rag_pipeline import RAGPipeline


class MockVectorStore:
    def __init__(self):
        self._documents = []
        self._index = type("obj", (object,), {"ntotal": 0})()

    def add_texts(self, texts, metadatas=None, ids=None):
        n = len(texts)
        self._documents.extend([
            {"text": t, "doc_id": f"doc_{i}"}
            for i, t in enumerate(texts)
        ])
        self._index.ntotal += n
        return [f"doc_{i}" for i in range(n)]

    def clear(self):
        self._documents.clear()
        self._index.ntotal = 0

    def load(self, directory):
        pass

    def get_stats(self):
        return {
            "total_vectors": self._index.ntotal,
            "dimension": 4,
            "total_documents": len(self._documents),
            "index_type": "MockIndex",
        }

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
        return "This is a test answer."

    async def stream(self, prompt):
        yield "This "
        yield "is "
        yield "a test answer."

    def invoke_async(self, prompt):
        import asyncio
        return asyncio.to_thread(self.invoke, prompt)


class TestRAGPipeline:
    @pytest.fixture
    def pipeline(self):
        return RAGPipeline(
            embedding_provider=MockEmbeddingProvider(),
            llm_provider=MockLLMProvider(),
            vectorstore=MockVectorStore(),
            config={"retrieval_strategy": "simple"},
        )

    def test_ingest_text(self, pipeline):
        ids = pipeline.ingest_text("hello world")
        assert len(ids) > 0

    def test_ingest_text_empty_raises(self, pipeline):
        with pytest.raises(Exception):
            pipeline.ingest_text("")

    def test_query(self, pipeline):
        pipeline.ingest_text("RAG stands for Retrieval-Augmented Generation.")
        result = pipeline.query("What is RAG?")
        assert "answer" in result
        assert "sources" in result
        assert "elapsed" in result

    def test_query_no_docs(self, pipeline):
        result = pipeline.query("What is RAG?")
        assert "answer" in result

    def test_retrieve_only(self, pipeline):
        pipeline.ingest_text("Some content here.")
        result = pipeline.retrieve_only("content")
        assert "results" in result
        assert result["total"] >= 1

    def test_set_retrieval_strategy(self, pipeline):
        pipeline.set_retrieval_strategy("mmr")
        assert pipeline.retriever.name == "mmr"

    def test_clear_index(self, pipeline):
        pipeline.ingest_text("hello")
        assert pipeline._vectorstore._index.ntotal > 0
        pipeline.clear_index()
        assert pipeline._vectorstore._index.ntotal == 0

    def test_get_stats(self, pipeline):
        stats = pipeline.get_stats()
        assert "vectorstore" in stats
        assert "retrieval_strategy" in stats

    def test_query_async(self, pipeline):
        import asyncio

        pipeline.ingest_text("RAG stands for Retrieval-Augmented Generation.")
        result = asyncio.run(pipeline.query_async("What is RAG?"))
        assert "answer" in result

    def test_query_stream(self, pipeline):
        import asyncio

        pipeline.ingest_text("RAG stands for Retrieval-Augmented Generation.")

        async def run():
            tokens = []
            async for token in pipeline.query_stream("What is RAG?"):
                tokens.append(token)
            return "".join(tokens)

        result = asyncio.run(run())
        assert len(result) > 0

    def test_delete_documents(self, pipeline):
        ids = pipeline.ingest_text("hello world")
        deleted = pipeline.delete_documents(ids)
        assert deleted == len(ids)
