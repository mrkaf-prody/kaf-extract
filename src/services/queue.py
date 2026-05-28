"""Async job queue using arq for background extraction tasks.

Supports:
- Enqueuing extraction jobs with immediate job_id return.
- Polling for job results via GET /api/v1/extract/{job_id}.
- Batch extraction jobs via enqueue_batch_extraction.
- Webhook dispatch with retry + HMAC-SHA256 signing.
- Worker setup for background processing.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
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
    # Expects format: redis://[user:***@]host:port/db
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
    webhook_url: str | None = None,
) -> str:
    """Enqueue an extraction job and return the job ID.

    Args:
        url: The URL to extract data from.
        fields: The field definitions.
        api_key_id: Optional API key ID for tracking.
        webhook_url: Optional webhook URL to POST results to on completion.

    Returns:
        The arq job ID string.
    """
    pool = await get_arq_pool()

    job = await pool.enqueue_job(
        "run_extraction",
        url=url,
        fields=fields,
        api_key_id=api_key_id,
        webhook_url=webhook_url,
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


async def enqueue_batch_extraction(
    urls: list[str],
    fields: list[dict],
    api_key_id: str | None = None,
    webhook_url: str | None = None,
) -> str:
    """Enqueue a batch extraction job and return the job ID.

    Args:
        urls: List of URLs to extract data from.
        fields: The field definitions.
        api_key_id: Optional API key ID for tracking.
        webhook_url: Optional webhook URL to POST results to on completion.

    Returns:
        The arq job ID string.
    """
    pool = await get_arq_pool()

    job = await pool.enqueue_job(
        "run_batch_extraction",
        urls=urls,
        fields=fields,
        api_key_id=api_key_id,
        webhook_url=webhook_url,
        _job_id=str(uuid.uuid4()),
    )

    job_id = job.job_id
    _job_registry[job_id] = {
        "urls": urls,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
        "api_key_id": api_key_id,
    }

    logger.info("Enqueued batch extraction job %s for %d urls", job_id, len(urls))
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
# Worker functions — these are what arq workers execute
# ---------------------------------------------------------------------------

async def run_extraction(
    ctx: dict[str, Any],
    url: str,
    fields: list[dict],
    api_key_id: str | None = None,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """Background extraction task executed by arq workers.

    Args:
        ctx: arq worker context dict (contains Redis pool, etc.).
        url: The URL to extract.
        fields: The extraction field definitions.
        api_key_id: Optional API key ID for tracking.
        webhook_url: Optional webhook URL to POST results to on completion.

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

        # Track usage (fire-and-forget — don't block the result)
        if api_key_id:
            try:
                from src.services.usage_alerts import increment_usage
                # Look up user_id from API key
                from src.models.apikey import _key_registry
                uid = _key_registry.get(api_key_id, {}).get("user_id")
                if uid:
                    from uuid import UUID
                    await increment_usage(UUID(uid))
            except Exception:
                pass

        # Dispatch webhook if URL provided
        if webhook_url:
            try:
                await dispatch_webhook(webhook_url, result)
            except Exception as e:
                logger.warning(
                    "Webhook dispatch failed for job (url=%s, webhook=%s): %s",
                    url, webhook_url, e,
                )

        return result

    except ExtractionError as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        result = {
            "status": "error",
            "data": None,
            "error": str(e),
            "metadata": {
                "url": url,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

        # Dispatch webhook even on error
        if webhook_url:
            try:
                await dispatch_webhook(webhook_url, result)
            except Exception as exc:
                logger.warning("Webhook dispatch failed for error job: %s", exc)

        return result


async def run_batch_extraction(
    ctx: dict[str, Any],
    urls: list[str],
    fields: list[dict],
    api_key_id: str | None = None,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """Background batch extraction task executed by arq workers.

    Args:
        ctx: arq worker context dict.
        urls: List of URLs to extract.
        fields: The extraction field definitions.
        api_key_id: Optional API key ID for tracking.
        webhook_url: Optional webhook URL to POST results to on completion.

    Returns:
        Dict with keys: status, results, total, succeeded, failed, metadata.
    """
    from src.services.extractor import ExtractionError, extractor_service

    start = time.monotonic()

    try:
        batch_results = await extractor_service.extract_batch(urls, fields, max_concurrent=5)
        duration_ms = int((time.monotonic() - start) * 1000)

        succeeded = sum(1 for r in batch_results if r["status"] == "success")
        failed = sum(1 for r in batch_results if r["status"] == "error")

        result = {
            "status": "success",
            "results": batch_results,
            "total": len(urls),
            "succeeded": succeeded,
            "failed": failed,
            "metadata": {
                "duration_ms": duration_ms,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

        # Dispatch webhook if URL provided
        if webhook_url:
            try:
                await dispatch_webhook(webhook_url, result)
            except Exception as e:
                logger.warning(
                    "Webhook dispatch failed for batch job (%d urls, webhook=%s): %s",
                    len(urls), webhook_url, e,
                )

        return result

    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        result = {
            "status": "error",
            "results": [],
            "total": len(urls),
            "succeeded": 0,
            "failed": len(urls),
            "error": str(e),
            "metadata": {
                "duration_ms": duration_ms,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

        if webhook_url:
            try:
                await dispatch_webhook(webhook_url, result)
            except Exception as exc:
                logger.warning("Webhook dispatch failed for batch error: %s", exc)

        return result


# ---------------------------------------------------------------------------
# Webhook dispatch with retry + HMAC-SHA256 signing
# ---------------------------------------------------------------------------

WEBHOOK_RETRY_DELAYS = [1, 4, 16]  # exponential backoff delays in seconds


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    """Create an HMAC-SHA256 signature for a JSON payload.

    Args:
        payload: The dict to sign (will be JSON-serialized with sorted keys).
        secret: The secret key for HMAC.

    Returns:
        Hex-encoded HMAC-SHA256 signature.
    """
    body = json.dumps(payload, sort_keys=True, default=str)
    mac = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()


def verify_signature(payload: dict[str, Any], signature: str, secret: str) -> bool:
    """Verify an HMAC-SHA256 signature for a JSON payload (constant-time).

    Args:
        payload: The dict that was signed.
        signature: The hex-encoded HMAC-SHA256 signature to verify.
        secret: The secret key for HMAC.

    Returns:
        True if the signature matches, False otherwise.
    """
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)


async def dispatch_webhook(
    webhook_url: str,
    payload: dict[str, Any],
    max_retries: int = 3,
) -> bool:
    """Dispatch a webhook callback with retry and HMAC-SHA256 signing.

    Detects Slack webhook URLs and formats the message using Slack Block Kit.
    For non-Slack URLs, sends the raw JSON payload with X-Kaf-Signature header.

    Retries with exponential backoff: 1s, 4s, 16s.

    Args:
        webhook_url: The URL to POST the payload to.
        payload: The JSON-serializable payload.
        max_retries: Maximum number of retry attempts (default 3).

    Returns:
        True if the webhook was delivered successfully, False otherwise.
    """
    is_slack = "hooks.slack.com" in webhook_url

    if is_slack:
        # Format as a Slack Block Kit message
        from src.services.slack import _build_slack_payload

        extraction_url = payload.get("metadata", {}).get("url", "unknown")
        status = payload.get("status", "unknown")
        data = payload.get("data")
        job_id = payload.get("metadata", {}).get("job_id")

        slack_payload = _build_slack_payload(
            url=extraction_url,
            status=status,
            data=data,
            job_id=job_id,
        )
        body = json.dumps(slack_payload, default=str)
        headers = {"Content-Type": "application/json"}
    else:
        # Standard webhook with HMAC signature
        signature = sign_payload(payload, settings.jwt_secret)
        headers = {
            "Content-Type": "application/json",
            "X-Kaf-Signature": signature,
        }
        body = json.dumps(payload, default=str)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook_url,
                    content=body,
                    headers=headers,
                )
                # Consider 2xx as success
                if 200 <= response.status_code < 300:
                    logger.info(
                        "Webhook dispatched to %s (attempt %d, status %d)",
                        webhook_url, attempt + 1, response.status_code,
                    )
                    return True
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(
                        "Webhook attempt %d to %s failed: %s",
                        attempt + 1, webhook_url, last_error,
                    )
        except Exception as e:
            last_error = str(e)
            logger.warning(
                "Webhook attempt %d to %s raised: %s",
                attempt + 1, webhook_url, e,
            )

        # Retry with exponential backoff (except after the last attempt)
        if attempt < max_retries:
            delay = WEBHOOK_RETRY_DELAYS[attempt] if attempt < len(WEBHOOK_RETRY_DELAYS) else 16
            logger.info("Retrying webhook in %ds...", delay)
            await asyncio.sleep(delay)

    logger.error(
        "Webhook dispatch to %s failed after %d attempts. Last error: %s",
        webhook_url, max_retries + 1, last_error,
    )
    return False


# ---------------------------------------------------------------------------
# Worker settings for `arq` CLI
# ---------------------------------------------------------------------------

class WorkerSettings:
    """Settings for `arq worker` command.

    Usage:
        arq src.services.queue.WorkerSettings
    """

    functions: list = [run_extraction, run_batch_extraction]
    redis_settings = _build_redis_settings()
    max_jobs: int = 10
    job_timeout: int = 300  # 5 minutes for batch extraction
    keep_result: int = 600  # Keep results for 10 minutes
    poll_delay: float = 0.5
    health_check_interval: int = 30

    # Note: use a module-level factory so that settings are re-evaluated
    # each time arq loads the worker (picks up env changes)

    def __init__(self) -> None:
        self.redis_settings = _build_redis_settings()
