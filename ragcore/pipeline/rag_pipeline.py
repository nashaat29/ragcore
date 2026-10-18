from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from ragcore.cache.semantic_cache import SemanticCache
from ragcore.core.config import settings
from ragcore.core.exceptions import GuardrailViolationError, PipelineError
from ragcore.core.logger import generate_correlation_id, get_logger
from ragcore.embeddings.provider import EmbeddingProvider
from ragcore.ingestion.chunker import SemanticChunker
from ragcore.ingestion.loader import DocumentLoader, load_directory
from ragcore.llm.chain import RAGChain
from ragcore.llm.provider import LLMProvider
from ragcore.monitoring.metrics import Timer, metrics
from ragcore.retrieval.base import BaseRetriever
from ragcore.retrieval.ensemble import EnsembleRetriever
from ragcore.retrieval.hybrid import HybridRetriever
from ragcore.retrieval.mmr import MMRRetriever
from ragcore.retrieval.simple import SimpleRetriever
from ragcore.safety import GuardrailResult, SafetyGuard
from ragcore.vectorstore.faiss_store import FAISSVectorStore
from ragcore.vectorstore.index_manager import IndexManager

logger = get_logger("ragcore.pipeline")

RETRIEVER_REGISTRY: dict[str, type[BaseRetriever]] = {
    "simple": SimpleRetriever,
    "mmr": MMRRetriever,
    "hybrid": HybridRetriever,
    "ensemble": EnsembleRetriever,
}


class RAGPipeline:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        llm_provider: LLMProvider | None = None,
        vectorstore: FAISSVectorStore | None = None,
        config: dict[str, Any] | None = None,
    ):
        self.config = config or {}
        self._embedding_provider = embedding_provider or EmbeddingProvider()
        self._llm_provider = llm_provider or LLMProvider()
        self._vectorstore = vectorstore or FAISSVectorStore(
            embedding_provider=self._embedding_provider,
        )
        self._index_manager = IndexManager()
        self._chain = RAGChain(self._llm_provider)
        self._chunker = SemanticChunker(embedding_provider=self._embedding_provider)
        self._cache = SemanticCache() if settings.cache_enabled else None
        self._retriever: BaseRetriever | None = None
        self._safety = SafetyGuard(self.config)

        self._load_active_index()

    def _load_active_index(self) -> None:
        try:
            self._index_manager.load_active_index(self._vectorstore)
        except Exception as e:
            logger.debug(f"No active index to load (or failed): {e}")

    @property
    def retriever(self) -> BaseRetriever:
        if self._retriever is None:
            strategy = self.config.get("retrieval_strategy", settings.retrieval_strategy)
            self._retriever = self._build_retriever(strategy)
        return self._retriever

    def _build_retriever(self, strategy: str) -> BaseRetriever:
        cls = RETRIEVER_REGISTRY.get(strategy)
        if cls is None:
            logger.warning(f"Unknown retriever '{strategy}', falling back to 'simple'")
            cls = SimpleRetriever

        retriever_config = dict(self.config)

        return cls(
            vectorstore=self._vectorstore,
            embedding_provider=self._embedding_provider,
            config=retriever_config,
        )

    def set_retrieval_strategy(self, strategy: str) -> None:
        self._retriever = self._build_retriever(strategy)
        logger.info(f"Retrieval strategy set to '{strategy}'")

    # --- Guardrail helpers ---

    @staticmethod
    def _new_guard_state() -> dict[str, Any]:
        return {"checks": [], "dropped_chunks": 0, "action": "pass"}

    @staticmethod
    def _apply_guard(state: dict[str, Any], res: GuardrailResult) -> None:
        state["checks"].extend(c.to_dict() for c in res.checks)
        state["dropped_chunks"] += res.dropped_chunks
        if res.triggered and state["action"] == "pass":
            state["action"] = res.action

    @staticmethod
    def _blocked_guard_info(e: GuardrailViolationError) -> dict[str, Any]:
        return {
            "triggered": True,
            "action": "block",
            "checks": e.checks,
            "dropped_chunks": 0,
        }

    def _guard_info(self, state: dict[str, Any]) -> dict[str, Any] | None:
        if not self._safety.enabled:
            return None
        return {
            "triggered": state["action"] != "pass",
            "action": state["action"],
            "checks": state["checks"],
            "dropped_chunks": state["dropped_chunks"],
        }

    def _guard_input(
        self,
        question: str,
        chat_history: list[dict[str, str]] | None,
        state: dict[str, Any],
    ) -> None:
        if not self._safety.enabled:
            return
        self._apply_guard(state, self._safety.check_input(question))
        for m in (chat_history or [])[-6:]:
            content = str(m.get("content", "") or "")
            if content:
                self._apply_guard(state, self._safety.check_input(content))

    def _guard_retrieval(
        self, retrieved: list[dict[str, Any]], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        if not self._safety.enabled or not retrieved:
            return retrieved
        kept_texts, res = self._safety.check_retrieval([r.get("text", "") for r in retrieved])
        self._apply_guard(state, res)
        if res.dropped_chunks == 0:
            return retrieved
        kept_set = set(kept_texts)
        return [r for r in retrieved if r.get("text", "") in kept_set]

    def _guard_output(
        self,
        question: str,
        answer: str,
        retrieved: list[dict[str, Any]],
        state: dict[str, Any],
    ) -> None:
        if not self._safety.enabled:
            return
        evidence = [r.get("text", "") for r in retrieved]
        self._apply_guard(state, self._safety.check_output(answer, question, evidence))

    def ingest_text(self, text: str, metadata: dict[str, Any] | None = None) -> list[str]:
        generate_correlation_id()
        metadata = metadata or {}
        metadata.setdefault("source", "direct_text")

        with Timer(metrics, "ingestion_latency"):
            chunks = self._chunker.split_text(text, metadata)
            if not chunks:
                raise PipelineError("No chunks produced from text")

            texts = [c.text for c in chunks]
            metadatas = [c.metadata for c in chunks]
            doc_ids = self._vectorstore.add_texts(texts, metadatas)

        metrics.increment("ingestions_total")
        logger.info(f"Ingested text -> {len(chunks)} chunks, ids={doc_ids[:3]}...")
        return doc_ids

    def ingest_file(self, file_path: str, metadata: dict[str, Any] | None = None) -> list[str]:
        generate_correlation_id()
        metadata = metadata or {}

        with Timer(metrics, "ingestion_latency"):
            loader = DocumentLoader(file_path)
            docs = loader.load()
            all_ids: list[str] = []

            for doc in docs:
                doc_metadata = {**metadata, **doc.metadata}
                chunks = self._chunker.split_text(doc.page_content, doc_metadata)
                if chunks:
                    texts = [c.text for c in chunks]
                    metadatas = [c.metadata for c in chunks]
                    doc_ids = self._vectorstore.add_texts(texts, metadatas)
                    all_ids.extend(doc_ids)

        metrics.increment("ingestions_total")
        logger.info(f"Ingested file '{file_path}' -> {len(all_ids)} chunks")
        return all_ids

    def ingest_directory(self, dir_path: str, recursive: bool = True) -> list[str]:
        with Timer(metrics, "ingestion_latency"):
            docs = load_directory(dir_path, recursive=recursive)
            all_ids: list[str] = []
            for doc in docs:
                chunks = self._chunker.split_text(doc.page_content, doc.metadata)
                if chunks:
                    texts = [c.text for c in chunks]
                    metadatas = [c.metadata for c in chunks]
                    doc_ids = self._vectorstore.add_texts(texts, metadatas)
                    all_ids.extend(doc_ids)

        metrics.increment("ingestions_total")
        logger.info(f"Ingested directory '{dir_path}' -> {len(all_ids)} total chunks")
        return all_ids

    def query(
        self,
        question: str,
        k: int | None = None,
        chat_history: list[dict[str, str]] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        generate_correlation_id()
        start = time.time()
        k = k or settings.retrieval_top_k
        guard_state = self._new_guard_state()

        self._guard_input(question, chat_history, guard_state)

        if use_cache and self._cache:
            cached = self._cache.get(question)
            if cached is not None:
                elapsed = time.time() - start
                metrics.increment("cache_hits")
                metrics.increment("queries_total")
                logger.info(f"Cache hit for query (elapsed={elapsed:.3f}s)")
                cached["cached"] = True
                cached["elapsed"] = elapsed
                cached["guardrail"] = self._guard_info(guard_state)
                return cached

        metrics.increment("cache_misses")
        metrics.increment("queries_total")

        with Timer(metrics, "query_latency"):
            with Timer(metrics, "retrieval_latency"):
                try:
                    retrieved = self.retriever.retrieve(question, k=k)
                except Exception as e:
                    metrics.increment("errors_total")
                    raise PipelineError(f"Retrieval failed: {e}") from e

            retrieved = self._guard_retrieval(retrieved, guard_state)

            if not retrieved:
                answer = "I couldn't find any relevant information to answer this question."
                sources = []
            else:
                context = "\n\n".join(
                    f"[{i+1}] {r.get('text', '')}"
                    for i, r in enumerate(retrieved)
                )
                with Timer(metrics, "generation_latency"):
                    try:
                        answer = self._chain.generate(question, context, chat_history)
                    except Exception as e:
                        raise PipelineError(f"Generation failed: {e}") from e

                self._guard_output(question, answer, retrieved, guard_state)

                sources = [
                    {
                        "text": r.get("text", "")[:200],
                        "score": r.get("score", 0.0),
                        "metadata": {k: v for k, v in r.items() if k not in ("text", "score", "index", "ensemble_score", "contributors")},
                    }
                    for r in retrieved
                ]

        result = {
            "answer": answer,
            "sources": sources,
            "question": question,
            "k": k,
            "retrieval_strategy": self.retriever.name,
            "total_chunks": len(retrieved),
            "elapsed": time.time() - start,
            "cached": False,
            "guardrail": self._guard_info(guard_state),
        }

        if use_cache and self._cache and retrieved:
            self._cache.set(question, result)

        logger.info(f"Query completed (elapsed={result['elapsed']:.3f}s, chunks={len(retrieved)})")
        return result

    async def query_async(
        self,
        question: str,
        k: int | None = None,
        chat_history: list[dict[str, str]] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self.query, question, k, chat_history, use_cache)

    async def query_stream(
        self,
        question: str,
        k: int | None = None,
        chat_history: list[dict[str, str]] | None = None,
        use_cache: bool = True,
    ) -> AsyncIterator[str]:

        k = k or settings.retrieval_top_k
        start = time.time()
        guard_state = self._new_guard_state()

        try:
            await asyncio.to_thread(self._guard_input, question, chat_history, guard_state)
        except GuardrailViolationError as e:
            self._last_stream_result = {
                "answer": "",
                "sources": [],
                "total_chunks": 0,
                "elapsed": time.time() - start,
                "retrieval_strategy": self.retriever.name,
                "cached": False,
                "blocked": True,
                "guardrail": self._blocked_guard_info(e),
            }
            return

        if use_cache and self._cache:
            cached = self._cache.get(question)
            if cached is not None:
                elapsed = time.time() - start
                metrics.increment("cache_hits")
                metrics.increment("queries_total")
                logger.info(f"Cache hit for stream query (elapsed={elapsed:.3f}s)")
                cached["cached"] = True
                cached["elapsed"] = elapsed
                cached["guardrail"] = self._guard_info(guard_state)
                self._last_stream_result = cached
                answer = cached.get("answer", "")
                for char in answer:
                    yield char
                    await asyncio.sleep(0)
                metrics.record_timing("query_latency", time.time() - start)
                return

        metrics.increment("cache_misses")
        metrics.increment("queries_total")

        retrieved = await asyncio.to_thread(self.retriever.retrieve, question, k)
        retrieved = await asyncio.to_thread(self._guard_retrieval, retrieved, guard_state)

        if not retrieved:
            answer = "I couldn't find any relevant information to answer this question."
            self._last_stream_result = {
                "answer": answer,
                "sources": [],
                "total_chunks": 0,
                "elapsed": time.time() - start,
                "retrieval_strategy": self.retriever.name,
                "cached": False,
                "guardrail": self._guard_info(guard_state),
            }
            yield answer
            metrics.record_timing("query_latency", time.time() - start)
            return

        context = "\n\n".join(
            f"[{i+1}] {r.get('text', '')}"
            for i, r in enumerate(retrieved)
        )

        tokens = []
        async for chunk in self._chain.stream(question, context, chat_history):
            tokens.append(chunk)
            yield chunk

        answer = "".join(tokens)

        try:
            await asyncio.to_thread(self._guard_output, question, answer, retrieved, guard_state)
        except GuardrailViolationError as e:
            self._last_stream_result = {
                "answer": answer,
                "sources": [],
                "total_chunks": len(retrieved),
                "elapsed": time.time() - start,
                "retrieval_strategy": self.retriever.name,
                "cached": False,
                "blocked": True,
                "guardrail": self._blocked_guard_info(e),
            }
            return

        sources = [
            {
                "text": r.get("text", "")[:200],
                "score": r.get("score", 0.0),
                "metadata": {k: v for k, v in r.items() if k not in ("text", "score", "index", "ensemble_score", "contributors")},
            }
            for r in retrieved
        ]

        result = {
            "answer": answer,
            "sources": sources,
            "total_chunks": len(retrieved),
            "elapsed": time.time() - start,
            "retrieval_strategy": self.retriever.name,
            "cached": False,
            "guardrail": self._guard_info(guard_state),
        }

        self._last_stream_result = result

        if use_cache and self._cache and retrieved:
            self._cache.set(question, result)

        metrics.record_timing("query_latency", time.time() - start)

    def retrieve_only(self, question: str, k: int | None = None) -> dict[str, Any]:
        k = k or settings.retrieval_top_k
        guard_state = self._new_guard_state()
        self._guard_input(question, None, guard_state)
        with Timer(metrics, "retrieval_latency"):
            retrieved = self.retriever.retrieve(question, k=k)
        retrieved = self._guard_retrieval(retrieved, guard_state)
        return {
            "results": [
                {
                    "text": r.get("text", ""),
                    "score": r.get("score", 0.0),
                    "metadata": {k: v for k, v in r.items() if k not in ("text", "score", "index")},
                }
                for r in retrieved
            ],
            "total": len(retrieved),
            "retrieval_strategy": self.retriever.name,
            "guardrail": self._guard_info(guard_state),
        }

    def save_index(self, name: str | None = None) -> None:
        name = name or settings.index_name
        self._index_manager.save_index(name, self._vectorstore)

    def load_index(self, name: str) -> None:
        self._index_manager.load_index(name, self._vectorstore)

    def delete_index(self, name: str) -> None:
        self._index_manager.delete_index(name)

    def clear_index(self) -> None:
        self._vectorstore.clear()

    def delete_documents(self, doc_ids: list[str]) -> int:
        return self._vectorstore.delete(doc_ids)

    def get_stats(self) -> dict[str, Any]:
        return {
            "vectorstore": self._vectorstore.get_stats(),
            "retrieval_strategy": self.retriever.name,
            "active_index": self._index_manager.get_active_index_name(),
            "available_indexes": [m["name"] for m in self._index_manager.list_indexes()],
        }
