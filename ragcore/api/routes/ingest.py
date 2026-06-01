from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from ragcore.api.deps import limiter
from ragcore.api.models import (
    DeleteRequest,
    DeleteResponse,
    IngestResponse,
    IngestTextRequest,
)
from ragcore.core.config import settings
from ragcore.core.logger import get_logger
from ragcore.pipeline.rag_pipeline import RAGPipeline

logger = get_logger("ragcore.api.routes.ingest")

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.post("/text", response_model=IngestResponse)
@limiter.limit(settings.rate_limit_ingest)
async def ingest_text(request: Request, req: IngestTextRequest):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    doc_ids = await asyncio.to_thread(pipeline.ingest_text, req.text, req.metadata)
    return IngestResponse(
        doc_ids=doc_ids,
        chunk_count=len(doc_ids),
        message=f"Ingested {len(doc_ids)} chunks",
    )


@router.post("/file", response_model=IngestResponse)
@limiter.limit(settings.rate_limit_ingest)
async def ingest_file(request: Request, file: UploadFile = File(...)):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    temp_dir = Path(pipeline.config.get("data_dir", "./rag_data")) / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = os.path.basename(file.filename or "upload")
    temp_path = temp_dir / safe_filename

    try:
        with open(temp_path, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)
        doc_ids = await asyncio.to_thread(pipeline.ingest_file, str(temp_path))
        return IngestResponse(
            doc_ids=doc_ids,
            chunk_count=len(doc_ids),
            message=f"Ingested {len(doc_ids)} chunks from {file.filename}",
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/directory", response_model=IngestResponse)
@limiter.limit(settings.rate_limit_ingest)
async def ingest_directory(request: Request, path: str, recursive: bool = True):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    data_dir = Path(pipeline.config.get("data_dir", "./rag_data")).resolve()
    requested_path = Path(path).resolve()
    try:
        requested_path.relative_to(data_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside allowed data directory")
    doc_ids = await asyncio.to_thread(pipeline.ingest_directory, str(requested_path), recursive=recursive)
    return IngestResponse(
        doc_ids=doc_ids,
        chunk_count=len(doc_ids),
        message=f"Ingested {len(doc_ids)} chunks from directory",
    )


@router.delete("/{doc_id}", response_model=DeleteResponse)
@limiter.limit(settings.rate_limit_ingest)
async def delete_document(request: Request, doc_id: str):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    deleted = await asyncio.to_thread(pipeline.delete_documents, [doc_id])
    return DeleteResponse(deleted_count=deleted)


@router.delete("/", response_model=DeleteResponse)
@limiter.limit(settings.rate_limit_ingest)
async def delete_documents(request: Request, req: DeleteRequest):
    from ragcore.api.server import get_pipeline

    pipeline: RAGPipeline = get_pipeline()
    deleted = await asyncio.to_thread(pipeline.delete_documents, req.doc_ids)
    return DeleteResponse(deleted_count=deleted)
