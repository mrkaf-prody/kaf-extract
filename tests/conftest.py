"""conftest.py — shared fixtures for Kaf Extract test suite."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock


@pytest.fixture(autouse=True, scope="session")
def patch_redis_for_tests():
    """Monkey-patch redis so all tests work without a live Redis server."""

    import redis.asyncio as aioredis

    class FakeRedis:
        """Minimal in-memory async Redis stub."""
        _store: dict[str, bytes] = {}

        async def get(self, key: str) -> bytes | None:
            return self._store.get(key)

        async def set(self, key: str, value: bytes | str, ex: int | None = None) -> bool:
            self._store[key] = value.encode() if isinstance(value, str) else value
            return True

        async def delete(self, *keys: str) -> int:
            count = 0
            for k in keys:
                if k in self._store:
                    del self._store[k]
                    count += 1
            return count

        async def keys(self, pattern: str) -> list[str]:
            return [k for k in self._store.keys() if pattern.rstrip("*") in k]

        async def expire(self, key: str, seconds: int) -> bool:
            return True

        async def ping(self) -> bool:
            return True

        async def aclose(self) -> None:
            pass

        async def sadd(self, key: str, value: str) -> int:
            return 1

        async def srem(self, key: str, value: str) -> int:
            return 1

        async def smembers(self, key: str) -> set[str]:
            return set()

        async def lpush(self, key: str, value: str) -> int:
            return 1

        async def lrange(self, key: str, start: int, end: int) -> list[bytes]:
            return []

        async def hset(self, key: str, mapping: dict) -> int:
            return 1

        async def hgetall(self, key: str) -> dict[str, bytes]:
            return {}

        async def flushall(self) -> bool:
            self._store.clear()
            return True

        async def eval(self, script: str, numkeys: int, *args) -> int:
            return 1

        async def zremrangebyscore(self, key: str, min_score: str, max_score: str | int) -> int:
            return 0

        async def zadd(self, key: str, *args, **kwargs) -> int:
            return 1

        async def zcard(self, key: str) -> int:
            return 0

        async def zrange(self, key: str, start: int, end: int, withscores: bool = False) -> list:
            return []

    # Patch from_url to return our fake
    _orig_from_url = aioredis.Redis.from_url

    def _fake_from_url(*args, **kwargs):
        return FakeRedis()

    aioredis.Redis.from_url = _fake_from_url
    yield
    # Restore on exit
    aioredis.Redis.from_url = _orig_from_url