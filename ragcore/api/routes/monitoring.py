from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ragcore.core.config import settings
from ragcore.core.logger import get_logger
from ragcore.monitoring.metrics import metrics
from ragcore.pipeline.rag_pipeline import RAGPipeline

logger = get_logger("ragcore.api.routes.monitoring")

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

SERVER_START_TIME = time.time()


@router.get("/stats")
async def get_monitoring_stats():
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    pipeline_stats = await asyncio.to_thread(pipeline.get_stats)

    counters = {}
    for key in ("queries_total", "ingestions_total", "cache_hits", "cache_misses", "errors_total"):
        counters[key] = metrics.get_counter(key)

    timings = {}
    for key in ("query_latency", "ingestion_latency", "retrieval_latency", "generation_latency"):
        stats = metrics.get_timing_stats(key)
        if stats:
            timings[key] = stats

    return {
        "uptime_seconds": time.time() - SERVER_START_TIME,
        "counters": counters,
        "timings": timings,
        "pipeline": {
            "vector_count": pipeline_stats.get("vectorstore", {}).get("total_vectors", 0),
            "retrieval_strategy": pipeline_stats.get("retrieval_strategy", "unknown"),
            "active_index": pipeline_stats.get("active_index", None),
            "available_indexes": pipeline_stats.get("available_indexes", []),
        },
    }


@router.get("/logs")
async def get_logs(lines: int = 100):
    log_file = Path(settings.log_file)
    if not log_file.exists():
        return {"logs": []}

    try:
        content = log_file.read_text(encoding="utf-8", errors="replace")
        log_lines = content.strip().split("\n")
        return log_lines[-lines:]
    except Exception as e:
        logger.error(f"Failed to read log file: {e}")
        return {"logs": [], "error": str(e)}


@router.get("/logs/stream")
async def stream_logs(request: Request):
    log_file = Path(settings.log_file)

    async def event_generator():
        last_position = 0
        if log_file.exists():
            try:
                content = log_file.read_text(encoding="utf-8", errors="replace")
                lines = content.strip().split("\n")
                last_lines = lines[-50:]
                if last_lines:
                    yield f"data: {json.dumps(last_lines)}\n\n"
                    last_position = len(content.encode("utf-8"))
            except Exception:
                pass

        try:
            async with asyncio.timeout(300):
                while True:
                    if await request.is_disconnected():
                        break

                    try:
                        if log_file.exists():
                            current_size = log_file.stat().st_size
                            if current_size > last_position:
                                with open(log_file, "rb") as f:
                                    f.seek(last_position)
                                    new_data = f.read(current_size - last_position)
                                    last_position = current_size

                                if new_data:
                                    text = new_data.decode("utf-8", errors="replace")
                                    new_lines = [ln for ln in text.split("\n") if ln.strip()]
                                    if new_lines:
                                        yield f"data: {json.dumps(new_lines)}\n\n"
                    except Exception:
                        pass

                    await asyncio.sleep(0.5)
        except TimeoutError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
