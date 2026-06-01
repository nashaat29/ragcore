from __future__ import annotations

import httpx
from fastapi import APIRouter

from ragcore._version import __version__
from ragcore.api.models import HealthResponse
from ragcore.core.config import settings
from ragcore.core.logger import get_logger

logger = get_logger("ragcore.api.routes.health")

router = APIRouter(tags=["Health"])


async def check_ollama() -> tuple[bool, str]:
    try:
        base_url = settings.llm_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            if response.status_code == 200:
                return True, "healthy"
            return False, f"status_{response.status_code}"
    except httpx.ConnectError:
        return False, "connection_refused"
    except httpx.TimeoutException:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:50]


async def check_vectorstore() -> tuple[bool, str]:
    try:
        from ragcore.api.server import get_pipeline
        pipeline = get_pipeline()
        stats = pipeline.get_stats()
        vector_stats = stats.get("vectorstore", {})
        count = vector_stats.get("total_vectors", 0)
        return True, f"healthy ({count} vectors)"
    except Exception as e:
        return False, str(e)[:50]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    ollama_ok, ollama_status = await check_ollama()
    vector_ok, vector_status = await check_vectorstore()

    all_healthy = ollama_ok and vector_ok

    return HealthResponse(
        status="ok" if all_healthy else "degraded",
        version=__version__,
        components={
            "api": "healthy",
            "ollama": ollama_status,
            "vectorstore": vector_status,
        },
    )


@router.get("/health/live")
async def liveness_check():
    return {"status": "alive", "version": __version__}


@router.get("/health/ready")
async def readiness_check():
    ollama_ok, _ = await check_ollama()
    if not ollama_ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Ollama not available")
    return {"status": "ready", "version": __version__}
