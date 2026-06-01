from ragcore._version import __version__, __version_info__

# Public API
from ragcore.api.server import RAGApp, RAGClient

# Re-export key classes for direct import
from ragcore.core.config import Settings
from ragcore.embeddings.provider import EmbeddingProvider
from ragcore.ingestion.chunker import SemanticChunker
from ragcore.ingestion.loader import DocumentLoader
from ragcore.llm.provider import LLMProvider
from ragcore.pipeline.rag_pipeline import RAGPipeline
from ragcore.vectorstore.faiss_store import FAISSVectorStore
from ragcore.vectorstore.index_manager import IndexManager

__all__ = [
    "__version__",
    "__version_info__",
    # Apps
    "RAGApp",
    "RAGClient",
    "RAGPipeline",
    # Config
    "Settings",
    # Providers
    "EmbeddingProvider",
    "LLMProvider",
    # Ingestion
    "SemanticChunker",
    "DocumentLoader",
    # Vector Store
    "FAISSVectorStore",
    "IndexManager",
]

__app_name__ = "ragcore"
__description__ = "Open-source RAG framework with FAISS + Ollama"
