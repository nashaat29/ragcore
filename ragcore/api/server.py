from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from ragcore._version import __version__
from ragcore.api.deps import limiter, rate_limit_handler
from ragcore.api.middleware import setup_middleware
from ragcore.api.routes.health import router as health_router
from ragcore.api.routes.ingest import router as ingest_router
from ragcore.api.routes.manage import router as manage_router
from ragcore.api.routes.monitoring import router as monitoring_router
from ragcore.api.routes.query import router as query_router
from ragcore.core.config import settings as app_settings
from ragcore.core.logger import get_logger, setup_logger
from ragcore.pipeline.rag_pipeline import RAGPipeline

logger = get_logger("ragcore.api.server")

_pipeline: RAGPipeline | None = None
_pipeline_lock = threading.Lock()


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        with _pipeline_lock:
            if _pipeline is None:
                _pipeline = RAGPipeline()
    return _pipeline


def reset_pipeline() -> None:
    global _pipeline
    with _pipeline_lock:
        _pipeline = None


async def check_ollama_health() -> tuple[bool, str]:
    try:
        base_url = app_settings.llm_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            if response.status_code == 200:
                return True, "healthy"
            return False, f"unexpected status: {response.status_code}"
    except httpx.ConnectError:
        return False, "connection_failed"
    except httpx.TimeoutException:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logger()
    get_pipeline()
    logger.info("RAGCore API starting up")

    ollama_ok, ollama_status = await check_ollama_health()
    if not ollama_ok:
        logger.warning(f"Ollama health check failed: {ollama_status}")
    else:
        logger.info("Ollama connection verified")

    yield

    logger.info("RAGCore API shutting down")
    reset_pipeline()


def create_app(
    config: dict[str, Any] | None = None,
    pipeline: RAGPipeline | None = None,
    title: str = "RAGCore API",
) -> FastAPI:
    global _pipeline
    if pipeline is not None:
        _pipeline = pipeline

    app = FastAPI(
        title=title,
        version=__version__,
        description="Open-source RAG API powered by FAISS + Ollama",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    setup_middleware(app)

    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    app.include_router(manage_router)
    app.include_router(monitoring_router)

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(static_dir / "index.html"))

    @app.get("/monitoring")
    async def serve_monitoring():
        return FileResponse(str(static_dir / "monitoring.html"))

    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name

    return app


class RAGApp:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._pipeline = RAGPipeline(config=self.config)
        self._app = create_app(config=self.config, pipeline=self._pipeline)

    @property
    def app(self) -> FastAPI:
        return self._app

    @property
    def pipeline(self) -> RAGPipeline:
        return self._pipeline

    def serve(self, host: str | None = None, port: int | None = None) -> None:
        host = host or app_settings.server_host
        port = port or app_settings.server_port
        logger.info(f"Starting RAGCore server on {host}:{port}")
        uvicorn.run(
            self._app,
            host=host,
            port=port,
            reload=app_settings.server_reload,
            workers=app_settings.server_workers,
            log_level=app_settings.log_level.lower(),
        )


class RAGClient:
    def __init__(self, pipeline: RAGPipeline | None = None):
        self._pipeline = pipeline or RAGPipeline()

    async def query(self, question: str, k: int | None = None, **kwargs) -> dict[str, Any]:
        return await self._pipeline.query_async(question, k=k, **kwargs)

    def query_sync(self, question: str, k: int | None = None, **kwargs) -> dict[str, Any]:
        return self._pipeline.query(question, k=k, **kwargs)

    def ingest_text(self, text: str, metadata: dict | None = None) -> list[str]:
        return self._pipeline.ingest_text(text, metadata)

    def ingest_file(self, file_path: str, metadata: dict | None = None) -> list[str]:
        return self._pipeline.ingest_file(file_path, metadata)
