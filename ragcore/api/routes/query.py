from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ragcore.api.deps import limiter
from ragcore.api.models import (
    QueryRequest,
    QueryResponse,
    RetrieveOnlyRequest,
    RetrieveOnlyResponse,
    SourceInfo,
    StreamQueryRequest,
)
from ragcore.core.config import settings
from ragcore.core.logger import get_logger

logger = get_logger("ragcore.api.routes.query")

router = APIRouter(tags=["Query"])


@router.post("/query", response_model=QueryResponse)
@limiter.limit(settings.rate_limit_query)
async def query(request: Request, req: QueryRequest):
    from ragcore.api.server import get_pipeline

    pipeline = get_pipeline()
    if req.retrieval_strategy:
        pipeline.set_retrieval_strategy(req.retrieval_strategy)
    result = await asyncio.to_thread(
        pipeline.query,
        question=req.question,
        k=req.k,
        chat_history=req.chat_history,
        use_cache=req.use_cache,
    )
    return QueryResponse(
        answer=result.get("answer", ""),
        sources=[SourceInfo(**s) for s in result.get("sources", [])],
        question=result.get("question", req.question),
        k=result.get("k", req.k or 4),
        retrieval_strategy=result.get("retrieval_strategy", ""),
        total_chunks=result.get("total_chunks", 0),
        elapsed=result.get("elapsed", 0.0),
        cached=result.get("cached", False),
    )


@router.post("/query/stream")
@limiter.limit(settings.rate_limit_query)
async def query_stream(request: Request, req: StreamQueryRequest):
    from ragcore.api.server import get_pipeline

    pipeline = get_pipeline()
    if req.retrieval_strategy:
        pipeline.set_retrieval_strategy(req.retrieval_strategy)

    stream = pipeline.query_stream(
        question=req.question,
        k=req.k,
        chat_history=req.chat_history,
        use_cache=req.use_cache,
    )

    async def generate():
        async for token in stream:
            yield f"data: {json.dumps({'token': token}, default=str)}\n\n"
        result = getattr(pipeline, '_last_stream_result', None) or {}
        yield f"data: {json.dumps({'event': 'done', 'result': result}, default=str)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/query/retrieve", response_model=RetrieveOnlyResponse)
@limiter.limit(settings.rate_limit_query)
async def retrieve_only(request: Request, req: RetrieveOnlyRequest):
    from ragcore.api.server import get_pipeline

    pipeline = get_pipeline()
    if req.retrieval_strategy:
        pipeline.set_retrieval_strategy(req.retrieval_strategy)
    result = await asyncio.to_thread(pipeline.retrieve_only, req.question, k=req.k)
    return RetrieveOnlyResponse(**result)
