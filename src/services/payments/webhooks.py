"""Webhook idempotency / deduplication helpers for payment providers.

Uses Redis to ensure payment provider webhooks are processed only once.
"""

from __future__ import annotations

import logging

from src.services.cache import get_redis

logger = logging.getLogger(__name__)

WEBHOOK_DEDUP_TTL_SECONDS = 86_400  # 24 hours


async def is_webhook_processed(event_id: str) -> bool:
    """Return True if the webhook event has already been processed.

    If Redis is unavailable the check fails open (returns False) so that
    the webhook is still processed rather than dropped.
    """
    if not event_id:
        return False
    try:
        r = await get_redis()
        result = await r.get(f"webhook:processed:{event_id}")
        return result is not None
    except Exception as exc:
        logger.warning("Redis error during webhook dedup check: %s", exc)
        return False


async def mark_webhook_processed(
    event_id: str, ttl: int = WEBHOOK_DEDUP_TTL_SECONDS
) -> None:
    """Mark a webhook event as processed in Redis.

    If Redis is unavailable the error is logged but not raised so that
    request processing is not blocked.
    """
    if not event_id:
        return
    try:
        r = await get_redis()
        await r.setex(f"webhook:processed:{event_id}", ttl, "1")
        logger.debug("Marked webhook %s as processed (ttl=%ds)", event_id, ttl)
    except Exception as exc:
        logger.warning("Redis error marking webhook processed: %s", exc)
