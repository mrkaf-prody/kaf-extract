"""Thread-safe metrics tracking for the Kaf Extract service.

Tracks:
- requests_total: total number of extraction requests
- cache_hits: number of cache hits
- cache_misses: number of cache misses
- total_duration_ms: cumulative extraction duration (for avg calculation)
- error_count: number of extraction errors
- uptime_seconds: time since module first imported (approximate)
"""

from __future__ import annotations

import threading
import time

# Uptime tracking
_start_time: float = time.monotonic()

# Thread-safe counters
_lock = threading.Lock()

_requests_total: int = 0
_cache_hits: int = 0
_cache_misses: int = 0
_total_duration_ms: float = 0.0
_error_count: int = 0


def _incr(name: str, delta: int | float = 1) -> None:
    """Increment a metric counter by delta (thread-safe)."""
    global _requests_total, _cache_hits, _cache_misses, _total_duration_ms, _error_count
    with _lock:
        if name == "requests_total":
            _requests_total += int(delta)
        elif name == "cache_hits":
            _cache_hits += int(delta)
        elif name == "cache_misses":
            _cache_misses += int(delta)
        elif name == "total_duration_ms":
            _total_duration_ms += float(delta)
        elif name == "error_count":
            _error_count += int(delta)


def record_request() -> None:
    """Record an extraction request."""
    _incr("requests_total")


def record_cache_hit() -> None:
    """Record a cache hit."""
    _incr("cache_hits")


def record_cache_miss() -> None:
    """Record a cache miss."""
    _incr("cache_misses")


def record_duration(duration_ms: float) -> None:
    """Record extraction duration in milliseconds."""
    _incr("total_duration_ms", duration_ms)


def record_error() -> None:
    """Record an extraction error."""
    _incr("error_count")


def get_metrics() -> dict:
    """Return a snapshot of all current metrics."""
    with _lock:
        requests = _requests_total
        cache_hits = _cache_hits
        cache_misses = _cache_misses
        total_dur = _total_duration_ms
        errors = _error_count

    uptime = time.monotonic() - _start_time
    avg_duration = total_dur / requests if requests > 0 else 0.0

    return {
        "requests_total": requests,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "avg_duration_ms": round(avg_duration, 2),
        "error_count": errors,
        "uptime_seconds": round(uptime, 2),
    }
