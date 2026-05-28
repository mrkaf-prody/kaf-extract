"""GET /metrics — Service metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from src.db import async_session_factory
from src.services.metrics import get_metrics as get_app_metrics

router = APIRouter(tags=["metrics"])


async def _check_db() -> str:
    """Check database connectivity with a simple SELECT 1."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return "healthy"
    except Exception:
        return "unhealthy"


async def _check_redis() -> str:
    """Check Redis connectivity with PING."""
    try:
        from src.services.cache import _redis as redis_client
        if redis_client is None:
            # Try connecting lazily
            from src.services.cache import connect_redis
            redis_client = await connect_redis()
        await redis_client.ping()
        return "healthy"
    except Exception:
        return "unavailable"


@router.get("/metrics")
async def metrics():
    """Return service metrics including DB and Redis status.

    Metrics tracked:
    - requests_total, cache_hits, cache_misses
    - avg_duration_ms, error_count, uptime_seconds
    - db_status, redis_status
    """
    app_metrics = get_app_metrics()

    # Check dependencies
    db_status = await _check_db()
    redis_status = await _check_redis()

    # Get queue depth (pending jobs in arq)
    queue_depth = 0
    try:
        from src.services.queue import _job_registry
        pending = sum(1 for j in _job_registry.values() if j.get("status") in ("queued", "in_progress", "deferred"))
        queue_depth = pending
    except Exception:
        pass

    return {
        **app_metrics,
        "queue_depth": queue_depth,
        "db_status": db_status,
        "redis_status": redis_status,
    }
