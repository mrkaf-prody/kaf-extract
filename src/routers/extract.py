"""POST /api/v1/extract — Data extraction endpoint.

Supports:
- Synchronous extraction with Redis caching (cache check + store).
- Async extraction via ?async=true → returns job_id, poll with GET /extract/{job_id}.
- Batch extraction POST /extract/batch with parallel Crawl4AI arun_many().
- Webhook callbacks with HMAC-SHA256 signing via webhook_url field.
- Per-API-key sliding window rate limiting via Redis.
"""

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.models.apikey import verify_api_key
from src.models.extract import (
    AIExtractRequest,
    AIExtractResponse,
    BatchExtractRequest,
    BatchExtractResponse,
    BatchResult,
    ExtractMetadata,
    ExtractRequest,
    ExtractResponse,
    ScreenshotData,
    ScreenshotRequest,
    ScreenshotResponse,
)
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
    format: str | None = Query(
        None,
        description="Export format: 'csv' (flat JSON→CSV) or 'markdown' (Crawl4AI markdown output). "
                    "Content negotiation via Accept header also supported as fallback.",
    ),
):
    """Extract structured data from a URL using CSS selectors or AI.

    Supports multiple extraction types per field:
    - text / html / attribute / exists: CSS-selector-based extraction via Crawl4AI
    - markdown: returns the page content as markdown
    - screenshot: returns a base64-encoded screenshot
    - ai: uses LLM extraction via Ollama (requires 'instruction' per field)

    Use ?async=true to enqueue the extraction and receive an immediate job_id.
    Poll for results with GET /api/v1/extract/{job_id}.
    Set webhook_url for async callback delivery on completion.
    """
    fields = _build_fields(body)
    url = str(body.url)

    # --- Resolve export format (query param > Accept header) ---
    resolved_format = format
    if resolved_format is None:
        accept = request.headers.get("Accept", "")
        if "text/csv" in accept:
            resolved_format = "csv"
        elif "text/markdown" in accept or "text/plain" in accept:
            resolved_format = "markdown"

    # --- Async mode: enqueue and return job_id ---
    if async_mode:
        from src.services.queue import enqueue_extraction

        api_key_id = str(key_info.get("id", key_info.get("label", "")))
        job_id = await enqueue_extraction(
            url, fields,
            api_key_id=api_key_id,
            webhook_url=body.webhook_url,
        )

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

    # If markdown format requested, ensure we capture the markdown
    wants_csv = resolved_format == "csv"
    wants_export_markdown = resolved_format == "markdown"

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

    # --- P2-5: Apply export format transforms ---
    if wants_csv:
        data = _json_to_csv(data)
    elif wants_export_markdown:
        # Re-extract with explicit markdown to get Crawl4AI markdown
        # If the user didn't ask for markdown, do a second-lightweight extract
        has_md = any(f.get("type") == "markdown" for f in fields)
        if not has_md:
            try:
                md_result = await extractor_service.extract(url, [
                    {"name": "markdown", "selector": "", "type": "markdown"},
                ])
                data = {"markdown": md_result.get("markdown", "")}
            except Exception:
                data = {"markdown": ""}
        else:
            # User already had markdown in fields, just return it
            pass

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
# Batch extraction endpoint
# ---------------------------------------------------------------------------

@router.post("/extract/batch", response_model=BatchExtractResponse)
async def batch_extract(
    request: Request,
    body: BatchExtractRequest,
    key_info: dict = Depends(check_rate_limit_dependency),
    async_mode: bool = Query(False, alias="async", description="Enqueue as async job and return job_id"),
):
    """Extract structured data from multiple URLs in parallel.

    Uses Crawl4AI's arun_many() with MemoryAdaptiveDispatcher for
    concurrent crawling with automatic backpressure.

    Supports up to 50 URLs per request.
    All URLs share the same extraction schema.

    Use ?async=true to enqueue as an async job and poll with GET /api/v1/extract/{job_id}.
    Set webhook_url for async callback delivery on completion.
    """
    fields = _build_fields_from_schema(body.schema)

    # --- Async mode ---
    if async_mode:
        from src.services.queue import enqueue_batch_extraction

        api_key_id = str(key_info.get("id", key_info.get("label", "")))
        job_id = await enqueue_batch_extraction(
            body.urls, fields,
            api_key_id=api_key_id,
            webhook_url=body.webhook_url,
        )

        # Return as a batch response with a job_id in metadata
        return BatchExtractResponse(
            results=[],
            total=0,
            succeeded=0,
            failed=0,
            # Note: we can't add custom fields to BatchExtractResponse easily,
            # but the caller knows to poll GET /api/v1/extract/{job_id}
        )

    # --- Synchronous mode ---
    record_request()

    try:
        batch_results = await extractor_service.extract_batch(
            body.urls, fields, max_concurrent=5,
        )
    except Exception as e:
        record_error()
        raise HTTPException(status_code=422, detail=str(e))

    # Build response
    results = [
        BatchResult(
            url=r["url"],
            status=r["status"],
            data=r.get("data"),
            error=r.get("error"),
        )
        for r in batch_results
    ]

    succeeded = sum(1 for r in batch_results if r["status"] == "success")
    failed = sum(1 for r in batch_results if r["status"] == "error")

    return BatchExtractResponse(
        results=results,
        total=len(batch_results),
        succeeded=succeeded,
        failed=failed,
    )


def _build_fields_from_schema(schema) -> list[dict]:
    """Convert ExtractSchema into the dict format used by the extractor."""
    return [
        {
            "name": f.name,
            "selector": f.selector,
            "type": f.type,
            "attribute": f.attribute,
            "instruction": f.instruction,
        }
        for f in schema.fields
    ]


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
    Also works for batch extraction jobs.
    """
    from src.services.queue import get_job_status

    job = await get_job_status(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    status = job.get("status", "unknown")

    if status == "complete":
        result_data = job.get("result", {})
        # Check if this is a batch result (has "results" key)
        if isinstance(result_data, dict) and "results" in result_data:
            return ExtractResponse(
                status="success",
                data={
                    "results": result_data.get("results", []),
                    "total": result_data.get("total", 0),
                    "succeeded": result_data.get("succeeded", 0),
                    "failed": result_data.get("failed", 0),
                },
                metadata=ExtractMetadata(
                    url="",
                    duration_ms=result_data.get("metadata", {}).get("duration_ms", 0),
                    timestamp=datetime.now(UTC).isoformat(),
                ),
            )
        else:
            return ExtractResponse(
                status="success",
                data=result_data.get("data"),
                metadata=ExtractMetadata(
                    url=result_data.get("metadata", {}).get("url", ""),
                    duration_ms=result_data.get("metadata", {}).get("duration_ms", 0),
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
                "error": result_data.get("error", "Unknown error") if isinstance(result_data, dict) else "Unknown error",
            },
            metadata=ExtractMetadata(
                url="",
                duration_ms=0,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )


# ---------------------------------------------------------------------------
# P2-5: JSON → CSV helper
# ---------------------------------------------------------------------------

import csv as _csv
import io as _io
import json as _json


def _json_to_csv(data: dict[str, Any]) -> str:
    """Convert a flat JSON dict to CSV text.

    Handles simple key-value pairs. Nested values are JSON-stringified.
    """
    if not data or not isinstance(data, dict):
        return ""

    # Flatten: if any value is a dict/list, JSON-stringify it
    flat: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            flat[key] = _json.dumps(value)
        elif value is None:
            flat[key] = ""
        else:
            flat[key] = str(value)

    output = _io.StringIO()
    writer = _csv.DictWriter(output, fieldnames=list(flat.keys()))
    writer.writeheader()
    writer.writerow(flat)
    return output.getvalue()


# ---------------------------------------------------------------------------
# P2-3: POST /api/v1/extract/ai — LLM-powered extraction
# ---------------------------------------------------------------------------


@router.post("/extract/ai", response_model=AIExtractResponse)
async def extract_ai(
    request: Request,
    body: AIExtractRequest,
    key_info: dict = Depends(check_rate_limit_dependency),
):
    """Extract data from a URL using natural-language instruction via Ollama.

    No CSS selectors needed — describe what you want in plain English.
    Supports model switching between kimi-k2.6:cloud and glm-5.1:cloud.

    Returns structured JSON matching the requested format.
    """
    record_request()

    start = time.monotonic()

    try:
        result = await extractor_service.extract_ai(
            url=str(body.url),
            instruction=body.instruction,
            model=body.model,
            output_format=body.format,
        )
    except ExtractionError as e:
        record_error()
        record_duration(int((time.monotonic() - start) * 1000))
        raise HTTPException(status_code=422, detail=str(e))

    duration_ms = result.get("duration_ms", int((time.monotonic() - start) * 1000))
    record_duration(duration_ms)

    return AIExtractResponse(
        status="success",
        data=result["data"],
        metadata=ExtractMetadata(
            url=str(body.url),
            duration_ms=duration_ms,
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


# ---------------------------------------------------------------------------
# P2-4: POST /api/v1/extract/screenshot — page screenshot
# ---------------------------------------------------------------------------


@router.post("/extract/screenshot", response_model=ScreenshotResponse)
async def extract_screenshot_endpoint(
    request: Request,
    body: ScreenshotRequest,
    key_info: dict = Depends(check_rate_limit_dependency),
):
    """Capture a screenshot of a web page.

    Returns a base64-encoded PNG screenshot.
    Supports full-page capture and element-specific screenshots via CSS selector.
    """
    record_request()

    start = time.monotonic()

    try:
        result = await extractor_service.extract_screenshot(
            url=str(body.url),
            full_page=body.full_page,
            selector=body.selector,
        )
    except ExtractionError as e:
        record_error()
        record_duration(int((time.monotonic() - start) * 1000))
        raise HTTPException(status_code=422, detail=str(e))

    duration_ms = result.get("duration_ms", int((time.monotonic() - start) * 1000))
    record_duration(duration_ms)

    return ScreenshotResponse(
        status="success",
        data=ScreenshotData(
            screenshot=result["screenshot"],
            format=result["format"],
        ),
        metadata=ExtractMetadata(
            url=str(body.url),
            duration_ms=duration_ms,
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )
