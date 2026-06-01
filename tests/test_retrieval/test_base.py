
from ragcore.retrieval.hybrid import HybridRetriever
from ragcore.retrieval.mmr import MMRRetriever
from ragcore.retrieval.simple import SimpleRetriever


class TestRetrieverBase:
    def test_retriever_name(self):
        assert SimpleRetriever.__name__ == "SimpleRetriever"
        assert MMRRetriever.__name__ == "MMRRetriever"
        assert HybridRetriever.__name__ == "HybridRetriever"

    def test_retriever_registry_keys(self):
        from ragcore.pipeline.rag_pipeline import RETRIEVER_REGISTRY
        assert "simple" in RETRIEVER_REGISTRY
        assert "mmr" in RETRIEVER_REGISTRY
        assert "hybrid" in RETRIEVER_REGISTRY
        assert "ensemble" in RETRIEVER_REGISTRY
