"""POST /api/v1/extract — Data extraction endpoint.

Supports:
- Synchronous extraction with Redis caching (cache check + store).
- Async extraction via ?async=true → returns job_id, poll with GET /extract/{job_id}.
- Per-API-key sliding window rate limiting via Redis.
"""

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.models.apikey import verify_api_key
from src.models.extract import ExtractMetadata, ExtractRequest, ExtractResponse
from src.services.extractor import ExtractionError, extractor_service
from src.services.metrics import (
    record_cache_hit,
    record_cache_miss,
    record_duration,
    record_error,
    record_request,
)

router = APIRouter(tags=["extract"])

# Rate limit headers (draft standard)
HEADER_RATELIMIT_LIMIT = "X-RateLimit-Limit"
HEADER_RATELIMIT_REMAINING = "X-RateLimit-Remaining"
HEADER_RATELIMIT_RESET = "X-RateLimit-Reset"
HEADER_RETRY_AFTER = "Retry-After"


async def validate_api_key(request: Request) -> dict:
    """Dependency: validate X-API-Key header (async DB-backed)."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    key_info = await verify_api_key(api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return key_info


async def check_rate_limit_dependency(
    request: Request,
    key_info: dict = Depends(validate_api_key),
) -> dict:
    """Dependency: enforce per-API-key rate limiting.

    Attaches rate-limit headers to the response via request.state.
    Raises 429 if limit exceeded.
    """
    from src.services.rate_limiter import check_rate_limit, get_retry_after

    # Determine the rate limit values for this key (from DB-backed key info)
    max_requests = key_info.get("rate_limit")
    # Convert to int if it's a string from the DB
    if isinstance(max_requests, str):
        try:
            max_requests = int(max_requests)
        except (ValueError, TypeError):
            from src.config import settings
            max_requests = settings.rate_limit_requests
    if max_requests is None:
        from src.config import settings
        max_requests = settings.rate_limit_requests

    api_key_id = str(key_info.get("id", key_info.get("label", "unknown")))

    result = await check_rate_limit(api_key_id, max_requests=max_requests)

    # Store headers on request.state for the router to attach to response
    request.state.rate_limit_headers = {
        HEADER_RATELIMIT_LIMIT: str(max_requests),
        HEADER_RATELIMIT_REMAINING: str(result.remaining),
        HEADER_RATELIMIT_RESET: str(int(result.reset_at)),
    }

    if not result.allowed:
        retry_after = get_retry_after(result.reset_at)
        request.state.rate_limit_headers[HEADER_RETRY_AFTER] = str(retry_after)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after}s.",
            headers=request.state.rate_limit_headers,
        )

    return key_info


def _build_fields(body: ExtractRequest) -> list[dict]:
    """Convert ExtractRequest fields into the dict format used by the extractor."""
    return [
        {
            "name": f.name,
            "selector": f.selector,
            "type": f.type,
            "attribute": f.attribute,
            "instruction": f.instruction,
        }
        for f in body.schema.fields
    ]


@router.post("/extract", response_model=ExtractResponse)
async def extract_data(
    request: Request,
    body: ExtractRequest,
    key_info: dict = Depends(check_rate_limit_dependency),
    async_mode: bool = Query(False, alias="async", description="Enqueue as async job and return job_id"),
):
    """Extract structured data from a URL using CSS selectors or AI.

    Supports multiple extraction types per field:
    - text / html / attribute / exists: CSS-selector-based extraction via Crawl4AI
    - markdown: returns the page content as markdown
    - screenshot: returns a base64-encoded screenshot
    - ai: uses LLM extraction via Ollama (requires 'instruction' per field)

    Use ?async=true to enqueue the extraction and receive an immediate job_id.
    Poll for results with GET /api/v1/extract/{job_id}.
    """
    fields = _build_fields(body)
    url = str(body.url)

    # --- Async mode: enqueue and return job_id ---
    if async_mode:
        from src.services.queue import enqueue_extraction

        api_key_id = str(key_info.get("id", key_info.get("label", "")))
        job_id = await enqueue_extraction(url, fields, api_key_id=api_key_id)

        # Build response with rate limit headers
        response = ExtractResponse(
            status="queued",
            data={"job_id": job_id, "status": "queued"},
            metadata=ExtractMetadata(
                url=url,
                duration_ms=0,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
        return response

    # --- Synchronous mode: check cache, extract, store ---
    from src.services.cache import cache_extraction_result, get_cached_result

    # Record a request
    record_request()

    # 1. Check Redis cache
    cached = await get_cached_result(url, fields)
    if cached is not None:
        record_cache_hit()
        return ExtractResponse(
            status="success",
            data=cached.get("data"),
            metadata=ExtractMetadata(
                url=url,
                duration_ms=0,
                timestamp=cached.get("metadata", {}).get(
                    "timestamp", datetime.now(UTC).isoformat()
                ),
            ),
        )

    # 2. Perform extraction
    start = time.monotonic()

    # Record cache miss (we're about to extract)
    record_cache_miss()

    try:
        data = await extractor_service.extract(url, fields)
    except ExtractionError as e:
        record_error()
        record_duration(int((time.monotonic() - start) * 1000))
        raise HTTPException(status_code=422, detail=str(e))

    duration_ms = int((time.monotonic() - start) * 1000)
    timestamp = datetime.now(UTC).isoformat()

    # Record successful duration
    record_duration(duration_ms)

    result = {
        "status": "success",
        "data": data,
        "metadata": {
            "url": url,
            "duration_ms": duration_ms,
            "timestamp": timestamp,
        },
    }

    # 3. Store in cache (fire-and-forget, don't block on cache write)
    try:
        import asyncio
        asyncio.create_task(cache_extraction_result(url, fields, result, ttl=300))
    except Exception:
        pass  # Don't fail the request if caching fails

    return ExtractResponse(
        status="success",
        data=data,
        metadata=ExtractMetadata(
            url=url,
            duration_ms=duration_ms,
            timestamp=timestamp,
        ),
    )


# ---------------------------------------------------------------------------
# Job polling endpoint
# ---------------------------------------------------------------------------

class JobStatusResponse(ExtractResponse):
    """Extended response for async job polling."""


@router.get("/extract/{job_id}", response_model=JobStatusResponse)
async def get_extraction_job(
    job_id: str,
    key_info: dict = Depends(validate_api_key),
):
    """Poll for the result of an async extraction job.

    Returns the extraction result if the job is complete, or the current
    job status (queued / in_progress) with no result yet.
    """
    from src.services.queue import get_job_status

    job = await get_job_status(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    status = job.get("status", "unknown")

    if status == "complete":
        return ExtractResponse(
            status="success",
            data=job.get("result", {}).get("data"),
            metadata=ExtractMetadata(
                url=job.get("result", {}).get("metadata", {}).get("url", ""),
                duration_ms=job.get("result", {}).get("metadata", {}).get("duration_ms", 0),
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
    elif status == "queued":
        return ExtractResponse(
            status="queued",
            data={"job_id": job_id, "status": "queued"},
            metadata=ExtractMetadata(
                url="",
                duration_ms=0,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
    elif status in ("in_progress", "deferred"):
        return ExtractResponse(
            status="processing",
            data={"job_id": job_id, "status": status},
            metadata=ExtractMetadata(
                url="",
                duration_ms=0,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
    else:
        # Error or unknown status
        return ExtractResponse(
            status="error",
            data={
                "job_id": job_id,
                "status": status,
                "error": job.get("result", {}).get("error", "Unknown error"),
            },
            metadata=ExtractMetadata(
                url="",
                duration_ms=0,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )
