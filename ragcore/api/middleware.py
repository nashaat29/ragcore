from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ragcore._version import __version__
from ragcore.core.config import settings
from ragcore.core.exceptions import RAGCoreError
from ragcore.core.logger import correlation_id, generate_correlation_id, get_logger

logger = get_logger("ragcore.api.middleware")


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        cid = request.headers.get("X-Correlation-ID", generate_correlation_id())
        correlation_id.set(cid)
        start = time.time()

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-RAGCore-Version"] = __version__

        elapsed = time.time() - start
        response.headers["X-Elapsed-Ms"] = str(round(elapsed * 1000, 2))
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        try:
            return await call_next(request)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "HTTPException",
                    "detail": e.detail,
                    "correlation_id": correlation_id.get(),
                },
            )
        except RAGCoreError as e:
            status_mapping: dict[type[RAGCoreError], int] = {}
            from ragcore.core.exceptions import (
                ConfigurationError,
                IndexNotFoundError,
                UnsupportedFileTypeError,
            )
            status_mapping = {
                IndexNotFoundError: status.HTTP_404_NOT_FOUND,
                UnsupportedFileTypeError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            status_code = status_mapping.get(type(e), status.HTTP_400_BAD_REQUEST)
            logger.error(f"RAGCore error: {e.message}", details=e.details)
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": e.__class__.__name__,
                    "detail": e.message,
                    "correlation_id": correlation_id.get(),
                },
            )
        except Exception as e:
            logger.exception(f"Unhandled error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "InternalServerError",
                    "detail": "An unexpected error occurred",
                    "correlation_id": correlation_id.get(),
                },
            )


class InputValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path

        if path in ["/ingest/text", "/ingest/file"] or path.startswith("/query"):
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    size_bytes = int(content_length)
                    max_bytes = settings.max_file_size_mb * 1024 * 1024
                    if size_bytes > max_bytes:
                        return JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content={
                                "error": "PayloadTooLarge",
                                "detail": f"Request too large. Maximum allowed: {settings.max_file_size_mb}MB",
                                "correlation_id": correlation_id.get(),
                            },
                        )
                except ValueError:
                    pass

        return await call_next(request)


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        expose_headers=["X-Correlation-ID", "X-RAGCore-Version", "X-Elapsed-Ms"],
    )
    app.add_middleware(InputValidationMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(CorrelationMiddleware)
