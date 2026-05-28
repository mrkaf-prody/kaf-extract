"""API Key verification — database-backed with bcrypt."""

import asyncio
from datetime import UTC, datetime

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import async_session_factory

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory fallback for backward compat during transition
# Format: {hashed_key: {"label": "dev-key", "rate_limit": 100}}
_fallback_keys: dict[str, dict] = {}


def _register_dev_key() -> None:
    """Register the default dev API key in the fallback store."""
    from src.config import settings
    if settings.dev_api_key not in _fallback_keys:
        _fallback_keys[pwd_context.hash(settings.dev_api_key)] = {
            "label": "dev-default",
            "rate_limit": 100,
            "tier": "hobby",
        }


_register_dev_key()


def _verify_in_memory(key: str) -> dict | None:
    """Check fallback in-memory keys (dev key)."""
    for hashed, meta in _fallback_keys.items():
        if pwd_context.verify(key, hashed):
            return meta
    return None


async def verify_api_key(key: str) -> dict | None:
    """Verify an API key against the database and return its metadata, or None.

    Falls back to in-memory dev key if database is unavailable.
    """
    # First check in-memory for dev key (fast path)
    in_memory_result = _verify_in_memory(key)
    if in_memory_result:
        return in_memory_result

    # Query the database
    try:
        async with async_session_factory() as session:
            from src.models.sql_models import ApiKey, User

            # Get all active API keys
            result = await session.execute(
                select(ApiKey, User)
                .join(User, ApiKey.user_id == User.id)
                .where(ApiKey.status == "active", User.status == "active")
            )
            rows = result.all()

            for api_key, user in rows:
                if pwd_context.verify(key, api_key.key_hash):
                    # Update last_used_at
                    api_key.last_used_at = datetime.now(UTC)
                    await session.commit()
                    return {
                        "id": str(api_key.id),
                        "user_id": str(api_key.user_id),
                        "label": api_key.label,
                        "tier": api_key.tier,
                        "rate_limit": api_key.rate_limit,
                        "email": user.email,
                        "role": user.role,
                    }
    except Exception:
        pass  # Database unavailable, fall through

    return None


# Synchronous wrapper for backward compat in non-async contexts
_loop: asyncio.AbstractEventLoop | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        try:
            _loop = asyncio.get_running_loop()
        except RuntimeError:
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
    return _loop


def verify_api_key_sync(key: str) -> dict | None:
    """Synchronous version of verify_api_key (for backward compat)."""
    # In-memory fast path
    in_memory_result = _verify_in_memory(key)
    if in_memory_result:
        return in_memory_result

    loop = _get_loop()
    if loop.is_running():
        # We're inside an event loop, use a new one
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(verify_api_key(key))
        finally:
            new_loop.close()
    return loop.run_until_complete(verify_api_key(key))


def get_api_key_info(key: str) -> dict | None:
    """Synchronous metadata lookup (for backward compat)."""
    return verify_api_key_sync(key)
