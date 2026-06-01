from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from ragcore.core.config import settings


class BaseQueryModel(BaseModel):
    question: str = Field(..., min_length=1)
    k: int | None = Field(default=None, ge=1)

    @field_validator("question")
    @classmethod
    def validate_question_length(cls, v: str) -> str:
        if len(v) > settings.max_query_length:
            raise ValueError(f"Question too long. Maximum allowed: {settings.max_query_length} characters")
        return v

    @field_validator("k")
    @classmethod
    def validate_k(cls, v: int | None) -> int | None:
        if v is not None and v > settings.max_k:
            raise ValueError(f"k too large. Maximum allowed: {settings.max_k}")
        return v


# --- Ingestion ---
class IngestTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text content to ingest")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def validate_text_length(cls, v: str) -> str:
        if len(v) > settings.max_text_length:
            raise ValueError(f"Text too long. Maximum allowed: {settings.max_text_length} characters")
        return v


class IngestResponse(BaseModel):
    status: str = "ok"
    doc_ids: list[str] = Field(default_factory=list)
    chunk_count: int = 0
    message: str = ""


class DeleteRequest(BaseModel):
    doc_ids: list[str] = Field(..., min_length=1)


class DeleteResponse(BaseModel):
    status: str = "ok"
    deleted_count: int = 0


# --- Query ---
class QueryRequest(BaseQueryModel):
    retrieval_strategy: str | None = Field(default=None, description="Override retrieval strategy")
    chat_history: list[dict[str, str]] | None = Field(default=None)
    use_cache: bool = Field(default=True)


class SourceInfo(BaseModel):
    text: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    answer: str = ""
    sources: list[SourceInfo] = Field(default_factory=list)
    question: str = ""
    k: int = 4
    retrieval_strategy: str = ""
    total_chunks: int = 0
    elapsed: float = 0.0
    cached: bool = False


class StreamQueryRequest(BaseQueryModel):
    retrieval_strategy: str | None = None
    chat_history: list[dict[str, str]] | None = None
    use_cache: bool = Field(default=True)


class RetrieveOnlyRequest(BaseQueryModel):
    retrieval_strategy: str | None = None


class RetrieveOnlyResponse(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    retrieval_strategy: str = ""


# --- Management ---
class IndexSaveRequest(BaseModel):
    name: str | None = Field(default=None, description="Index name (default: config value)")


class IndexLoadRequest(BaseModel):
    name: str = Field(..., min_length=1)


class IndexInfo(BaseModel):
    name: str
    created_at: str | None = None
    updated_at: str | None = None
    vector_count: int = 0
    dimension: int = 0
    size_bytes: int = 0
    active: bool = False


class StatsResponse(BaseModel):
    vectorstore: dict[str, Any] = Field(default_factory=dict)
    retrieval_strategy: str = ""
    active_index: str | None = None
    available_indexes: list[str] = Field(default_factory=list)


# --- Health ---
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = ""
    components: dict[str, str] = Field(default_factory=dict)


# --- Error ---
class ErrorResponse(BaseModel):
    error: str = ""
    detail: str | None = None
    correlation_id: str | None = None
