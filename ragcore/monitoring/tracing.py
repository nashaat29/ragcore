from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

from ragcore.core.logger import get_logger

logger = get_logger("ragcore.monitoring.tracing")

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")


class TraceSpan:
    def __init__(self, name: str, attributes: dict[str, Any] | None = None):
        self.name = name
        self.attributes = attributes or {}
        self.trace_id = trace_id_var.get() or uuid.uuid4().hex[:16]
        self.span_id = uuid.uuid4().hex[:16]
        self.parent_span_id = span_id_var.get()
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def __enter__(self):
        import time
        self.start_time = time.time()
        trace_id_var.set(self.trace_id)
        span_id_var.set(self.span_id)
        logger.debug(f"Span start: {self.name}", extra={
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "attributes": self.attributes,
        })
        return self

    def __exit__(self, *args):
        import time
        self.end_time = time.time()
        duration = (self.end_time - self.start_time) * 1000
        logger.debug(f"Span end: {self.name} ({duration:.2f}ms)", extra={
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "duration_ms": round(duration, 2),
        })
        span_id_var.set(self.parent_span_id)


def trace(name: str, attributes: dict[str, Any] | None = None) -> TraceSpan:
    return TraceSpan(name, attributes)
