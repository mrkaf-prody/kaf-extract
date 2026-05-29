"""POST /api/v1/extract/session — Session-authenticated extraction endpoint.

Mirrors the API-key extract endpoints but uses JWT session auth.
Tracks usage via UsageAlert (monthly quota system).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.db import get_db
from src.middleware.auth import get_current_user
from src.models.extract import AIExtractRequest, AIExtractResponse, ExtractRequest, ExtractResponse
from src.models.sql_models import UsageAlert
from src.services.extractor import ExtractionError, extractor_service
from src.services.metrics import record_cache_hit, record_cache_miss, record_duration, record_error, record_request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/extract/session", tags=["extract"])


async def _track_and_check_limit(user_id: Any, db: AsyncSession) -> dict:
    """Retrieve user's usage limits and enforce monthly cap.

    Returns a dict with {id, rate_limit, tier, user_id, type}
    compatible with rate-limit dependency flow.
    """
    result = await db.execute(
        select(UsageAlert).where(UsageAlert.user_id == user_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        # Default
        return {
            "id": str(user_id),
            "type": "session",
            "rate_limit": 100,
            "tier": "hobby",
            "user_id": str(user_id),
            "monthly_limit": 1000,
            "current_usage": 0,
        }

    if alert.hard_cap is not None and alert.current_usage >= alert.hard_cap:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly hard cap reached ({alert.current_usage}/{alert.hard_cap}).",
        )

    if alert.current_usage >= alert.monthly_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly usage limit reached ({alert.current_usage}/{alert.monthly_limit}). Upgrade your plan.",
        )

    return {
        "id": str(user_id),
        "type": "session",
        "rate_limit": alert.monthly_limit,
        "tier": getattr(alert, "tier", "hobby"),
        "user_id": str(user_id),
        "monthly_limit": alert.monthly_limit,
        "current_usage": alert.current_usage,
    }


async def _increment_usage(user_id: Any, db: AsyncSession) -> None:
    """Increment usage counter for session-authenticated request."""
    result = await db.execute(
        select(UsageAlert).where(UsageAlert.user_id == user_id)
    )
    alert = result.scalar_one_or_none()
    if alert:
        alert.current_usage += 1
        await db.commit()


@router.post("", response_model=ExtractResponse)
async def extract_data_session(
    request: Request,
    body: ExtractRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Synchronous extraction for authenticated dashboard users."""
    user_id = current_user["user_id"]
    auth_info = await _track_and_check_limit(user_id, db)

    url = str(body.url)
    record_request()

    # Perform extraction
    from src.services.cache import cache_extraction_result, get_cached_result

    # Simple extraction fields (session users get best-effort extraction)
    fields = {"content": {"type": "markdown"}}

    # Check cache
    cached = await get_cached_result(url, fields)
    if cached is not None:
        record_cache_hit()
        await _increment_usage(user_id, db)
        return ExtractResponse(
            status="success",
            data=cached.get("data"),
            metadata=ExtractResponse.__fields__["metadata"].type_(
                url=url,
                duration_ms=0,
                timestamp=cached.get("metadata", {}).get("timestamp", datetime.now(UTC).isoformat()),
            ),
        )

    record_cache_miss()
    start = time.monotonic()
    try:
        data = await extractor_service.extract(url, fields)
    except ExtractionError as e:
        record_error()
        record_duration(int((time.monotonic() - start) * 1000))
        raise HTTPException(status_code=422, detail=str(e))

    duration_ms = int((time.monotonic() - start) * 1000)
    timestamp = datetime.now(UTC).isoformat()

    # Cache and track
    await cache_extraction_result(url, fields, {"data": data, "metadata": {"duration_ms": duration_ms, "timestamp": timestamp}})
    await _increment_usage(user_id, db)
    record_duration(duration_ms)

    return ExtractResponse(
        status="success",
        data=data,
        metadata=ExtractResponse.__fields__["metadata"].type_(
            url=url,
            duration_ms=duration_ms,
            timestamp=timestamp,
        ),
    )


@router.post("/ai", response_model=AIExtractResponse)
async def extract_ai_session(
    request: Request,
    body: AIExtractRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI-powered extraction for authenticated dashboard users."""
    user_id = current_user["user_id"]
    await _track_and_check_limit(user_id, db)

    url = str(body.url)
    record_request()

    start = time.monotonic()
    try:
        result = await extractor_service.extract_with_ai(
            url=url,
            instruction=body.prompt,
            include_markdown=body.include_markdown,
            include_screenshots=body.include_screenshots,
            include_links=body.include_links,
        )
    except Exception as e:
        record_error()
        record_duration(int((time.monotonic() - start) * 1000))
        raise HTTPException(status_code=422, detail=str(e))

    duration_ms = int((time.monotonic() - start) * 1000)
    timestamp = datetime.now(UTC).isoformat()
    await _increment_usage(user_id, db)
    record_duration(duration_ms)

    return AIExtractResponse(
        status="success",
        data=json.loads(result) if isinstance(result, str) else result,
        metadata=AIExtractResponse.__fields__["metadata"].type_(
            url=url,
            duration_ms=duration_ms,
            timestamp=timestamp,
        ),
    )
