from __future__ import annotations

import time

from ragcore.core.logger import get_logger

logger = get_logger("ragcore.monitoring.metrics")


class MetricsCollector:
    def __init__(self):
        self._counters: dict[str, int] = {}
        self._timers: dict[str, list[float]] = {}

    def increment(self, metric: str, value: int = 1) -> None:
        self._counters[metric] = self._counters.get(metric, 0) + value

    def record_timing(self, metric: str, elapsed: float) -> None:
        if metric not in self._timers:
            self._timers[metric] = []
        self._timers[metric].append(elapsed)
        if len(self._timers[metric]) > 1000:
            self._timers[metric] = self._timers[metric][-500:]

    def get_counter(self, metric: str) -> int:
        return self._counters.get(metric, 0)

    def get_timing_stats(self, metric: str) -> dict[str, float] | None:
        timings = self._timers.get(metric)
        if not timings:
            return None
        sorted_t = sorted(timings)
        n = len(sorted_t)
        return {
            "count": n,
            "min": sorted_t[0],
            "max": sorted_t[-1],
            "avg": sum(sorted_t) / n,
            "p50": sorted_t[n // 2],
            "p95": sorted_t[int(n * 0.95)],
            "p99": sorted_t[int(n * 0.99)],
        }

    def reset(self) -> None:
        self._counters.clear()
        self._timers.clear()


class Timer:
    def __init__(self, collector: MetricsCollector, metric: str):
        self._collector = collector
        self._metric = metric
        self._start: float = 0.0

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *args):
        elapsed = time.time() - self._start
        self._collector.record_timing(self._metric, elapsed)


metrics = MetricsCollector()
