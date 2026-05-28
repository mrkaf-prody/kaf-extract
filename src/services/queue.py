"""Async job queue using arq for background extraction tasks.

Supports:
- Enqueuing extraction jobs with immediate job_id return.
- Polling for job results via GET /api/v1/extract/{job_id}.
- Worker setup for background processing.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job, JobStatus

from src.config import settings

logger = logging.getLogger(__name__)

# Global arq pool (shared across requests)
_arq_pool: ArqRedis | None = None

# In-memory job registry for jobs enqueued via arq (job_id -> metadata)
# In production, this would be backed by Redis, but for simplicity we track
# job metadata in Redis directly via arq's built-in job storage.
_job_registry: dict[str, dict[str, Any]] = {}


def _build_redis_settings() -> RedisSettings:
    """Parse REDIS_URL into arq's RedisSettings."""
    url = settings.redis_url
    # Expects format: redis://[user:pass@]host:port/db
    # arq RedisSettings uses host/port/database/username/password
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or "0"),
        username=parsed.username or None,
        password=parsed.password or None,
    )


async def get_arq_pool() -> ArqRedis:
    """Get or lazily create the arq Redis connection pool."""
    global _arq_pool
    if _arq_pool is None:
        redis_settings = _build_redis_settings()
        _arq_pool = await create_pool(redis_settings)
        logger.info("Arq Redis connection pool created")
    return _arq_pool


async def close_arq_pool() -> None:
    """Close the arq Redis connection pool."""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None
        logger.info("Arq Redis connection pool closed")


async def enqueue_extraction(
    url: str,
    fields: list[dict],
    api_key_id: str | None = None,
) -> str:
    """Enqueue an extraction job and return the job ID.

    Args:
        url: The URL to extract data from.
        fields: The field definitions.
        api_key_id: Optional API key ID for tracking.

    Returns:
        The arq job ID string.
    """
    pool = await get_arq_pool()

    job = await pool.enqueue_job(
        "run_extraction",
        url=url,
        fields=fields,
        api_key_id=api_key_id,
        _job_id=str(uuid.uuid4()),
    )

    job_id = job.job_id
    _job_registry[job_id] = {
        "url": url,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
        "api_key_id": api_key_id,
    }

    logger.info("Enqueued extraction job %s for url=%s", job_id, url)
    return job_id


async def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Poll for the status and result of a previously enqueued job.

    Args:
        job_id: The arq job ID.

    Returns:
        Dict with keys: job_id, status, result (if complete), error (if failed),
        enqueue_time, start_time, finish_time. Returns None if job not found.
    """
    pool = await get_arq_pool()

    try:
        job = Job(job_id, pool)
        job_info = await job.info()

        if job_info is None:
            # Check in-memory registry as fallback
            return _job_registry.get(job_id)

        result: dict[str, Any] = {
            "job_id": job_id,
            "status": job_info.status,
            "enqueue_time": job_info.enqueue_time.isoformat() if job_info.enqueue_time else None,
            "start_time": job_info.start_time.isoformat() if job_info.start_time else None,
            "finish_time": job_info.finish_time.isoformat() if job_info.finish_time else None,
        }

        if job_info.status == JobStatus.complete:
            result_info = await job.result_info()
            if result_info and result_info.result is not None:
                result["result"] = json.loads(json.dumps(result_info.result, default=str))
        elif job_info.status == JobStatus.not_found:
            return None

        # Update in-memory registry
        if job_id in _job_registry:
            _job_registry[job_id]["status"] = job_info.status

        return result

    except Exception as e:
        logger.warning("Failed to fetch job status for %s: %s", job_id, e)
        return _job_registry.get(job_id)


# ---------------------------------------------------------------------------
# Worker function — this is what arq workers execute
# ---------------------------------------------------------------------------

async def run_extraction(
    ctx: dict[str, Any],
    url: str,
    fields: list[dict],
    api_key_id: str | None = None,
) -> dict[str, Any]:
    """Background extraction task executed by arq workers.

    Args:
        ctx: arq worker context dict (contains Redis pool, etc.).
        url: The URL to extract.
        fields: The extraction field definitions.
        api_key_id: Optional API key ID for tracking.

    Returns:
        Dict with keys: status, data, metadata.
    """
    from src.services.extractor import ExtractionError, extractor_service

    start = time.monotonic()

    try:
        data = await extractor_service.extract(url, fields)
        duration_ms = int((time.monotonic() - start) * 1000)

        result = {
            "status": "success",
            "data": data,
            "metadata": {
                "url": url,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

        # Cache the result
        try:
            from src.services.cache import cache_extraction_result
            await cache_extraction_result(url, fields, result, ttl=300)
        except Exception:
            logger.warning("Failed to cache extraction result", exc_info=True)

        return result

    except ExtractionError as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "error",
            "data": None,
            "error": str(e),
            "metadata": {
                "url": url,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }


# ---------------------------------------------------------------------------
# Worker settings for `arq` CLI
# ---------------------------------------------------------------------------

class WorkerSettings:
    """Settings for `arq worker` command.

    Usage:
        arq src.services.queue.WorkerSettings
    """

    functions: list = [run_extraction]
    redis_settings = _build_redis_settings()
    max_jobs: int = 10
    job_timeout: int = 120  # 2 minutes per extraction
    keep_result: int = 600  # Keep results for 10 minutes
    poll_delay: float = 0.5
    health_check_interval: int = 30

    # Note: use a module-level factory so that settings are re-evaluated
    # each time arq loads the worker (picks up env changes)

    def __init__(self) -> None:
        self.redis_settings = _build_redis_settings()
