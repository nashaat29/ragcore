from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from ragcore.api.deps import limiter
from ragcore.api.models import (
    IndexInfo,
    IndexLoadRequest,
    IndexSaveRequest,
    StatsResponse,
)
from ragcore.core.config import settings
from ragcore.core.logger import get_logger
from ragcore.pipeline.rag_pipeline import RAGPipeline

logger = get_logger("ragcore.api.routes.manage")

router = APIRouter(prefix="/manage", tags=["Management"])


@router.get("/index/stats", response_model=StatsResponse)
@limiter.limit(settings.rate_limit_default)
async def index_stats(request: Request):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    try:
        stats = await asyncio.to_thread(pipeline.get_stats)
        return StatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/index/save")
@limiter.limit(settings.rate_limit_default)
async def save_index(request: Request, req: IndexSaveRequest):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    try:
        await asyncio.to_thread(pipeline.save_index, req.name)
        return {"status": "ok", "message": f"Index '{req.name or 'default'}' saved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/index/load")
@limiter.limit(settings.rate_limit_default)
async def load_index(request: Request, req: IndexLoadRequest):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    try:
        await asyncio.to_thread(pipeline.load_index, req.name)
        return {"status": "ok", "message": f"Index '{req.name}' loaded"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/index/clear")
@limiter.limit(settings.rate_limit_default)
async def clear_index(request: Request):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    try:
        await asyncio.to_thread(pipeline.clear_index)
        return {"status": "ok", "message": "Index cleared"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/index/list", response_model=list[IndexInfo])
@limiter.limit(settings.rate_limit_default)
async def list_indexes(request: Request):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    try:
        indexes = await asyncio.to_thread(pipeline._index_manager.list_indexes)
        return [IndexInfo(**idx) for idx in indexes]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/retrieval/strategy")
@limiter.limit(settings.rate_limit_default)
async def set_retrieval_strategy(request: Request, strategy: str):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    try:
        await asyncio.to_thread(pipeline.set_retrieval_strategy, strategy)
        return {"status": "ok", "strategy": strategy}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/index/{name}")
@limiter.limit(settings.rate_limit_default)
async def delete_index(request: Request, name: str):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    try:
        await asyncio.to_thread(pipeline.delete_index, name)
        return {"status": "ok", "message": f"Index '{name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/config")
@limiter.limit(settings.rate_limit_default)
async def get_config(request: Request):
    return settings.model_dump()
