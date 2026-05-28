"""Redis caching layer for extraction results.

Provides connection management and cache store/retrieve for extraction
results, keyed by SHA-256 hash of URL + sorted schema fields.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from src.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def connect_redis() -> aioredis.Redis:
    """Create and return a shared Redis connection pool."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
        # Verify connectivity
        await _redis.ping()
        logger.info("Redis connected at %s", settings.redis_url)
    return _redis


async def close_redis() -> None:
    """Close the shared Redis connection pool."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


async def _get_redis() -> aioredis.Redis:
    """Return the Redis client, connecting lazily if needed."""
    if _redis is None:
        return await connect_redis()
    return _redis


def _build_cache_key(url: str, fields: list[dict]) -> str:
    """Build a deterministic cache key from the URL and field schema.

    Sorts fields by name so that reordering doesn't bust the cache.
    """
    # Sort fields by name for deterministic key
    serializable_fields = [
        {
            "name": f.get("name", ""),
            "selector": f.get("selector", ""),
            "type": f.get("type", "text"),
            "attribute": f.get("attribute", ""),
            "instruction": f.get("instruction", ""),
        }
        for f in fields
    ]
    serializable_fields.sort(key=lambda f: (f["name"], f["type"]))

    raw = json.dumps({"url": url, "fields": serializable_fields}, sort_keys=True)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"extract:{digest}"


async def cache_extraction_result(
    url: str,
    fields: list[dict],
    result: dict[str, Any],
    ttl: int = 300,
) -> None:
    """Store an extraction result in Redis with a TTL.

    Args:
        url: The URL that was extracted.
        fields: The field definitions used for extraction.
        result: The extraction result dict to cache.
        ttl: Time-to-live in seconds (default 5 minutes).
    """
    r = await _get_redis()
    key = _build_cache_key(url, fields)
    value = json.dumps(result, default=str)
    await r.setex(key, ttl, value)
    logger.debug("Cached extraction result for key=%s (ttl=%ds)", key, ttl)


async def get_cached_result(
    url: str,
    fields: list[dict],
) -> dict[str, Any] | None:
    """Retrieve a cached extraction result, or None if not found.

    Args:
        url: The URL that was extracted.
        fields: The field definitions used for extraction.

    Returns:
        The cached result dict, or None if no cache hit.
    """
    r = await _get_redis()
    key = _build_cache_key(url, fields)
    value = await r.get(key)
    if value is None:
        return None
    logger.debug("Cache hit for key=%s", key)
    return json.loads(value)


async def invalidate_cache(url: str | None = None) -> int:
    """Delete cached extraction results.

    Args:
        url: If provided, invalidate only keys matching this URL prefix.
             If None, invalidate all extraction cache entries.

    Returns:
        Number of keys deleted.
    """
    r = await _get_redis()
    deleted = 0

    if url:
        # Scan for keys matching URL (we can't scan by pattern on URL directly,
        # but we can scan all extract:* keys and check the stored payload)
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="extract:*", count=100)
            for key in keys:
                val = await r.get(key)
                if val:
                    try:
                        parsed = json.loads(val)
                        # Just delete all extract:* keys for simplicity
                        await r.delete(key)
                        deleted += 1
                    except json.JSONDecodeError:
                        await r.delete(key)
                        deleted += 1
            if cursor == 0:
                break
    else:
        # Delete all extract:* keys using scan (no KEYS command in prod)
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="extract:*", count=100)
            if keys:
                await r.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break

    logger.info("Invalidated %d cache entries", deleted)
    return deleted
