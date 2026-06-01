from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any


class TTLCache:
    def __init__(self, ttl: float = 300, maxsize: int = 1024):
        self._ttl = ttl
        self._maxsize = maxsize
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        timestamp, value = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self._maxsize:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]
        self._cache[key] = (time.time(), value)

    def clear(self) -> None:
        self._cache.clear()

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    @property
    def size(self) -> int:
        return len(self._cache)


def ttl_cache(ttl: float = 300, maxsize: int = 1024) -> Callable:
    cache = TTLCache(ttl=ttl, maxsize=maxsize)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = str(args) + str(sorted(kwargs.items()))
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.clear_cache = cache.clear
        wrapper.invalidate_cache = lambda *a, **kw: cache.invalidate(
            str(a) + str(sorted(kw.items()))
        )
        return wrapper

    return decorator
