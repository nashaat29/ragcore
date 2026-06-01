from __future__ import annotations

import sys
import uuid
from contextvars import ContextVar
from pathlib import Path

from loguru import logger as _base_logger

from ragcore.core.config import settings

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

COLORED_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level:8}</level>"
    " | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "{message}\n{exception}"
)


def setup_logger() -> None:
    for handler_id in list(_base_logger._core.handlers):
        _base_logger.remove(handler_id)

    _base_logger.add(
        sys.stdout,
        format=COLORED_FORMAT,
        level=settings.log_level.upper(),
        colorize=True,
        serialize=(settings.log_format == "json"),
    )

    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _base_logger.add(
        str(log_path),
        format=COLORED_FORMAT,
        level=settings.log_level.upper(),
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="gz",
        enqueue=True,
        serialize=True,
    )


def get_logger(name: str | None = None):
    if name:
        return _base_logger.bind(module=name)
    return _base_logger


def generate_correlation_id() -> str:
    cid = uuid.uuid4().hex[:12]
    correlation_id.set(cid)
    return cid


logger = get_logger("ragcore")
