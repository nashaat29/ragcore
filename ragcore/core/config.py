from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAGCORE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=False,
    )

    # --- LLM ---
    llm_model: str = Field(default="frob/qwen3.5-instruct:9b")
    llm_base_url: str = Field(default="http://127.0.0.1:11434")
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=4096, ge=1)
    llm_timeout: int = Field(default=120, ge=1)

    # --- Embeddings ---
    embedding_model: str = Field(default="nomic-embed-text:latest")
    embedding_base_url: str = Field(default="http://127.0.0.1:11434")

    # --- Chunking ---
    chunk_min_tokens: int = Field(default=200, ge=50)
    chunk_max_tokens: int = Field(default=1200, ge=100)
    chunk_overlap_tokens: int = Field(default=150, ge=0)
    chunk_similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

    # --- Retrieval ---
    retrieval_strategy: Literal["simple", "mmr", "hybrid", "ensemble"] = Field(default="simple")
    retrieval_top_k: int = Field(default=4, ge=1)
    retrieval_score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)

    # --- Cache ---
    cache_embedding_ttl: int = Field(default=86400, ge=0)
    cache_semantic_ttl: int = Field(default=3600, ge=0)
    cache_semantic_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    cache_lru_maxsize: int = Field(default=4096, ge=1)
    cache_enabled: bool = Field(default=True)

    # --- Data ---
    data_dir: str = Field(default="./rag_data")
    index_name: str = Field(default="default")

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_format: Literal["json", "colored"] = Field(default="json")
    log_file: str = ""
    log_rotation: str = Field(default="10 MB")
    log_retention: str = Field(default="30 days")

    # --- Server ---
    server_host: str = Field(default="127.0.0.1")
    server_port: int = Field(default=29000, ge=1, le=65535)
    server_reload: bool = Field(default=False)
    server_workers: int = Field(default=1, ge=1)

    # --- CORS ---
    cors_allow_origins: list[str] = Field(default=["http://localhost:29000"])
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # --- Rate Limiting ---
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_default: str = Field(default="100/minute")
    rate_limit_query: str = Field(default="20/minute")
    rate_limit_ingest: str = Field(default="10/minute")

    # --- Input Limits ---
    max_text_length: int = Field(default=100000, ge=1)
    max_file_size_mb: int = Field(default=50, ge=1)
    max_query_length: int = Field(default=4000, ge=1)
    max_k: int = Field(default=50, ge=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.log_file:
            self.log_file = str(Path(self.data_dir) / "logs" / "ragcore.log")

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def index_path(self) -> Path:
        return self.data_path / "indexes" / self.index_name

    @property
    def cache_path(self) -> Path:
        return self.data_path / "cache"

    @property
    def logs_path(self) -> Path:
        return self.data_path / "logs"


settings = Settings()
