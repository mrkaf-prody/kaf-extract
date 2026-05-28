"""Sliding window rate limiter per API key, backed by Redis.

Uses a sliding window algorithm with sorted-set (ZSET) per API key.
The window slides forward in time — only requests within the window count
against the limit. This is more accurate than fixed-window and avoids
burst-at-boundary problems.
"""

from __future__ import annotations

import logging
import time
from typing import NamedTuple

from src.config import settings
from src.services.cache import _get_redis

logger = logging.getLogger(__name__)


class RateLimitResult(NamedTuple):
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_at: float  # Unix timestamp when the window resets


async def check_rate_limit(
    api_key_id: str,
    max_requests: int | None = None,
    window_seconds: int | None = None,
) -> RateLimitResult:
    """Check if an API key is within its rate limit using sliding window.

    Args:
        api_key_id: Unique identifier for the API key (from auth).
        max_requests: Max requests allowed in the window. Defaults to settings.
        window_seconds: Window size in seconds. Defaults to settings.

    Returns:
        RateLimitResult with allowed, remaining, and reset_at fields.
    """
    if max_requests is None:
        max_requests = settings.rate_limit_requests
    if window_seconds is None:
        window_seconds = settings.rate_limit_window_seconds

    r = await _get_redis()
    now = time.time()
    window_start = now - window_seconds

    key = f"ratelimit:{api_key_id}"

    # Remove expired entries (older than window_start)
    await r.zremrangebyscore(key, "-inf", window_start)

    # Count how many requests are in the current window
    current_count = await r.zcard(key)

    if current_count >= max_requests:
        # Rate limited — calculate when the oldest entry expires
        oldest = await r.zrange(key, 0, 0, withscores=True)
        if oldest:
            reset_at = oldest[0][1] + window_seconds
        else:
            reset_at = now + window_seconds

        logger.warning(
            "Rate limit exceeded for key=%s: %d/%d requests",
            api_key_id[:16],
            current_count,
            max_requests,
        )
        return RateLimitResult(allowed=False, remaining=0, reset_at=reset_at)

    # Add current request with microsecond-precision timestamp to avoid collisions
    await r.zadd(key, {f"{now}:{current_count}": now})

    # Set TTL on the key so stale rate-limit keys get cleaned up
    await r.expire(key, window_seconds * 2)

    remaining = max_requests - current_count - 1
    reset_at = now + window_seconds

    logger.debug(
        "Rate limit check passed for key=%s: %d remaining",
        api_key_id[:16],
        remaining,
    )
    return RateLimitResult(allowed=True, remaining=remaining, reset_at=reset_at)


async def get_rate_limit_status(
    api_key_id: str,
    max_requests: int | None = None,
    window_seconds: int | None = None,
) -> RateLimitResult:
    """Check rate limit status without incrementing the counter.

    Args:
        api_key_id: Unique identifier for the API key.
        max_requests: Max requests allowed in the window (defaults to settings).
        window_seconds: Window size in seconds (defaults to settings).

    Returns:
        RateLimitResult with allowed, remaining, and reset_at.
    """
    if max_requests is None:
        max_requests = settings.rate_limit_requests
    if window_seconds is None:
        window_seconds = settings.rate_limit_window_seconds

    r = await _get_redis()
    now = time.time()
    window_start = now - window_seconds

    key = f"ratelimit:{api_key_id}"

    # Remove expired
    await r.zremrangebyscore(key, "-inf", window_start)

    current_count = await r.zcard(key)

    if current_count >= max_requests:
        oldest = await r.zrange(key, 0, 0, withscores=True)
        reset_at = oldest[0][1] + window_seconds if oldest else now + window_seconds
        return RateLimitResult(allowed=False, remaining=0, reset_at=reset_at)

    remaining = max_requests - current_count
    reset_at = now + window_seconds
    return RateLimitResult(allowed=True, remaining=remaining, reset_at=reset_at)


def get_retry_after(reset_at: float) -> int:
    """Calculate the Retry-After value in seconds from a reset timestamp."""
    return max(1, int(reset_at - time.time()))
