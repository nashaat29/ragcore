from __future__ import annotations

import re
from typing import Any

import numpy as np

from ragcore.core.config import settings
from ragcore.core.logger import get_logger
from ragcore.embeddings.provider import EmbeddingProvider
from ragcore.ingestion.preprocessor import preprocessor as text_preprocessor

logger = get_logger("ragcore.ingestion.chunker")

SENTENCE_BOUNDARIES = re.compile(
    r"(?<=[.!?…])\s+(?=[A-Z\"'«»„\u201c({])|(?<=\n)\s*(?=\n)|(?<=[:;])\s+"
)


class Chunk:
    def __init__(self, text: str, metadata: dict[str, Any] | None = None):
        self.text = text
        self.metadata = metadata or {}
        self._token_count: int | None = None

    @property
    def token_count(self) -> int:
        if self._token_count is None:
            self._token_count = self._estimate_tokens(self.text)
        return self._token_count

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // 4 + len(re.findall(r"\s", text)) // 2 or len(text)

    def __repr__(self) -> str:
        return f"Chunk(tokens={self.token_count}, meta={self.metadata})"


class SemanticChunker:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        config: dict[str, Any] | None = None,
    ):
        self._embedding_provider = embedding_provider or EmbeddingProvider()
        self.config = config or {}
        self.min_tokens = self.config.get("min_tokens", settings.chunk_min_tokens)
        self.max_tokens = self.config.get("max_tokens", settings.chunk_max_tokens)
        self.overlap_tokens = self.config.get("overlap_tokens", settings.chunk_overlap_tokens)
        self.similarity_threshold = self.config.get("similarity_threshold", settings.chunk_similarity_threshold)

    def split_text(self, text: str, metadata: dict[str, Any] | None = None) -> list[Chunk]:
        text = text_preprocessor.run(text)
        if not text.strip():
            return []

        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return [Chunk(text, metadata=metadata or {})]

        embeddings = self._embedding_provider.embed_documents(sentences)
        breakpoints = self._detect_boundaries(embeddings)
        chunks = self._build_chunks(sentences, breakpoints, metadata or {})

        chunks = self._merge_small_chunks(chunks)
        chunks = self._split_large_chunks(chunks)

        if self.overlap_tokens > 0:
            chunks = self._apply_overlap(chunks)

        for i, chunk in enumerate(chunks):
            chunk.metadata.setdefault("chunk_id", i)
            chunk.metadata.setdefault("chunk_count", len(chunks))

        if chunks:
            logger.info(
                f"Semantic chunker: {len(sentences)} sentences -> {len(chunks)} chunks "
                f"(min={min(c.token_count for c in chunks)}, "
                f"max={max(c.token_count for c in chunks)})"
            )
        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        parts = SENTENCE_BOUNDARIES.split(text)
        parts = [p.strip() for p in parts if p.strip()]
        if not parts:
            parts = [text.strip()]
        return parts

    def _detect_boundaries(self, embeddings: list[list[float]]) -> list[int]:
        if len(embeddings) < 2:
            return []

        emb_array = np.array(embeddings)
        emb_norm = emb_array / (np.linalg.norm(emb_array, axis=1, keepdims=True) + 1e-10)
        similarities = np.sum(emb_norm[:-1] * emb_norm[1:], axis=1)

        breakpoints: list[int] = []
        window_size = min(3, len(similarities))

        for i in range(len(similarities)):
            window_start = max(0, i - window_size + 1)
            window = similarities[window_start : i + 1]
            local_mean = np.mean(window)

            if similarities[i] < self.similarity_threshold and similarities[i] < local_mean * 0.9:
                breakpoints.append(i + 1)

        return breakpoints

    def _build_chunks(
        self, sentences: list[str], breakpoints: list[int], metadata: dict[str, Any]
    ) -> list[Chunk]:
        if not breakpoints:
            full_text = " ".join(sentences)
            return [Chunk(full_text, metadata=dict(metadata))]

        ranges: list[tuple[int, int]] = []
        start = 0
        for bp in breakpoints:
            if bp > start:
                ranges.append((start, bp))
            start = bp
        if start < len(sentences):
            ranges.append((start, len(sentences)))

        chunks: list[Chunk] = []
        for s, e in ranges:
            chunk_text = " ".join(sentences[s:e])
            chunk_meta = dict(metadata)
            chunk_meta["sentence_start"] = s
            chunk_meta["sentence_end"] = e
            chunks.append(Chunk(chunk_text, metadata=chunk_meta))

        return chunks

    def _merge_small_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        if len(chunks) <= 1:
            return chunks

        merged: list[Chunk] = []
        carry: Chunk | None = None

        for chunk in chunks:
            if carry is None:
                if chunk.token_count < self.min_tokens:
                    carry = chunk
                else:
                    merged.append(chunk)
            else:
                combined_tokens = carry.token_count + chunk.token_count
                if combined_tokens <= self.max_tokens:
                    carry = Chunk(
                        text=carry.text + " " + chunk.text,
                        metadata={**carry.metadata, **chunk.metadata},
                    )
                else:
                    merged.append(carry)
                    carry = chunk if chunk.token_count < self.min_tokens else None
                    if carry is None:
                        merged.append(chunk)

        if carry is not None:
            if merged:
                last = merged.pop()
                merged.append(
                    Chunk(
                        text=last.text + " " + carry.text,
                        metadata={**last.metadata, **carry.metadata},
                    )
                )
            else:
                merged.append(carry)

        return merged

    def _split_large_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        result: list[Chunk] = []
        for chunk in chunks:
            if chunk.token_count <= self.max_tokens:
                result.append(chunk)
            else:
                sentences = self._split_sentences(chunk.text)
                if len(sentences) <= 1:
                    result.append(chunk)
                    continue

                embeddings = self._embedding_provider.embed_documents(sentences)
                breakpoints = self._detect_boundaries(embeddings)

                if not breakpoints:
                    mid = len(sentences) // 2
                    breakpoints = [mid]

                sub_chunks = self._build_chunks(sentences, breakpoints, chunk.metadata)
                result.extend(self._split_large_chunks(sub_chunks))

        return result

    def _apply_overlap(self, chunks: list[Chunk]) -> list[Chunk]:
        if len(chunks) <= 1:
            return chunks

        overlapped: list[Chunk] = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                prev_chunk = overlapped[-1]
                prev_sentences = self._split_sentences(prev_chunk.text)
                overlap_text = ""
                overlap_tokens = 0
                for sent in reversed(prev_sentences):
                    sent_tokens = Chunk._estimate_tokens(sent)
                    if overlap_tokens + sent_tokens > self.overlap_tokens:
                        break
                    overlap_text = sent + " " + overlap_text
                    overlap_tokens += sent_tokens
                if overlap_text.strip():
                    chunk = Chunk(
                        text=overlap_text.strip() + " " + chunk.text,
                        metadata=dict(chunk.metadata),
                    )
            overlapped.append(chunk)

        return overlapped

    def split_documents(self, texts: list[str], metadata_list: list[dict] | None = None) -> list[Chunk]:
        if metadata_list is None:
            metadata_list = [{}] * len(texts)
        all_chunks: list[Chunk] = []
        for text, meta in zip(texts, metadata_list):
            all_chunks.extend(self.split_text(text, meta))
        return all_chunks
