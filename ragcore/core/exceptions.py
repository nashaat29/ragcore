from __future__ import annotations


class RAGCoreError(Exception):
    """Base exception for all ragcore errors."""

    def __init__(self, message: str = "", details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(RAGCoreError):
    """Raised when there's an issue with configuration."""


class IngestionError(RAGCoreError):
    """Raised when document ingestion fails."""


class UnsupportedFileTypeError(IngestionError):
    """Raised when file type is not supported."""


class ChunkingError(RAGCoreError):
    """Raised when semantic chunking fails."""


class EmbeddingError(RAGCoreError):
    """Raised when embedding generation fails."""


class VectorStoreError(RAGCoreError):
    """Raised on vector store operations failure."""


class IndexNotFoundError(VectorStoreError):
    """Raised when a requested index doesn't exist."""


class RetrievalError(RAGCoreError):
    """Raised when retrieval fails."""


class LLMError(RAGCoreError):
    """Raised when LLM call fails."""


class LLMTimeoutError(LLMError):
    """Raised when LLM call times out."""


class CacheError(RAGCoreError):
    """Raised when cache operation fails."""


class PipelineError(RAGCoreError):
    """Raised when the RAG pipeline fails."""


class GuardrailViolationError(RAGCoreError):
    """Raised when a safety guardrail blocks a request or a response."""

    def __init__(
        self,
        message: str = "Blocked by safety guardrail",
        *,
        stage: str = "",
        rail: str = "",
        checks: list[dict[str, str]] | None = None,
    ):
        details = {"stage": stage, "rail": rail, "action": "block"}
        super().__init__(message, details)
        self.stage = stage
        self.rail = rail
        self.checks = checks or []


class ServerError(RAGCoreError):
    """Raised on server-level errors."""
