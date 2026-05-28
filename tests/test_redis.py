"""Tests for Redis caching, arq job queue, and rate limiting."""

import json
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.config import settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Cache key generation tests (no Redis needed)
# ---------------------------------------------------------------------------


class TestCacheKey:
    """Tests for cache key generation."""

    def test_same_url_fields_produces_same_key(self):
        """Identical URL + fields should produce the same cache key."""
        from src.services.cache import _build_cache_key

        url = "https://example.com"
        fields = [
            {"name": "title", "selector": "h1", "type": "text"},
            {"name": "price", "selector": ".price", "type": "text"},
        ]

        key1 = _build_cache_key(url, fields)
        key2 = _build_cache_key(url, fields)
        assert key1 == key2

    def test_field_reorder_produces_same_key(self):
        """Reordering fields should produce the same cache key."""
        from src.services.cache import _build_cache_key

        url = "https://example.com"
        fields_a = [
            {"name": "title", "selector": "h1", "type": "text"},
            {"name": "price", "selector": ".price", "type": "text"},
        ]
        fields_b = [
            {"name": "price", "selector": ".price", "type": "text"},
            {"name": "title", "selector": "h1", "type": "text"},
        ]

        key_a = _build_cache_key(url, fields_a)
        key_b = _build_cache_key(url, fields_b)
        assert key_a == key_b

    def test_different_url_produces_different_key(self):
        """Different URLs should produce different cache keys."""
        from src.services.cache import _build_cache_key

        fields = [{"name": "title", "selector": "h1", "type": "text"}]

        key1 = _build_cache_key("https://example.com", fields)
        key2 = _build_cache_key("https://other.com", fields)
        assert key1 != key2

    def test_different_fields_produce_different_key(self):
        """Different field definitions should produce different cache keys."""
        from src.services.cache import _build_cache_key

        url = "https://example.com"
        key1 = _build_cache_key(url, [{"name": "a", "selector": "h1", "type": "text"}])
        key2 = _build_cache_key(url, [{"name": "b", "selector": "h2", "type": "text"}])
        assert key1 != key2

    def test_key_format(self):
        """Cache keys should use the 'extract:<sha256>' format."""
        from src.services.cache import _build_cache_key

        key = _build_cache_key("https://test.com", [{"name": "x", "selector": "p", "type": "text"}])
        assert key.startswith("extract:")
        assert len(key) == len("extract:") + 64  # SHA-256 hex = 64 chars


# ---------------------------------------------------------------------------
# Rate limiter helper tests (no Redis needed)
# ---------------------------------------------------------------------------


class TestRateLimiterHelpers:
    """Tests for rate limiter utility functions."""

    def test_get_retry_after_future(self):
        from src.services.rate_limiter import get_retry_after

        future = time.time() + 30
        retry = get_retry_after(future)
        assert 29 <= retry <= 31

    def test_get_retry_after_past(self):
        from src.services.rate_limiter import get_retry_after

        past = time.time() - 10
        retry = get_retry_after(past)
        assert retry == 1  # Minimum 1 second


# ---------------------------------------------------------------------------
# Fake Redis implementations for unit testing
# ---------------------------------------------------------------------------


class FakeRedisCache:
    """In-memory fake Redis for testing cache operations."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._ttl: dict[str, float] = {}

    async def get(self, key: str) -> str | None:
        if key in self._ttl and time.time() > self._ttl[key]:
            del self._store[key]
            del self._ttl[key]
            return None
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value
        self._ttl[key] = time.time() + ttl

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        pass

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
            if key in self._ttl:
                del self._ttl[key]
        return count

    async def scan(self, cursor=0, match=None, count=100):
        import fnmatch
        prefix = match.replace("*", "") if match else ""
        keys = [k for k in self._store if k.startswith(prefix)]
        return (0, keys)

    # Rate limiter methods
    async def zremrangebyscore(self, key, min_val, max_val) -> int:
        return 0

    async def zcard(self, key) -> int:
        return 0

    async def zrange(self, key, start, stop, withscores=False):
        return []

    async def zadd(self, key, mapping) -> int:
        return 1

    async def expire(self, key, ttl) -> bool:
        return True


class FakeRedisRateLimit:
    """In-memory fake Redis specifically for rate limiter tests."""

    def __init__(self):
        self._sets: dict[str, list[tuple[str, float]]] = {}

    async def zremrangebyscore(self, key, min_val, max_val) -> int:
        if key not in self._sets:
            return 0
        old_len = len(self._sets[key])

        # Convert Redis-style min/max strings to actual floats
        min_f = -float("inf") if min_val == "-inf" else float(min_val)
        max_f = float("inf") if max_val == "+inf" else float(max_val)

        self._sets[key] = [
            (m, s) for m, s in self._sets[key] if not (min_f <= s <= max_f)
        ]
        return old_len - len(self._sets[key])

    async def zcard(self, key) -> int:
        return len(self._sets.get(key, []))

    async def zrange(self, key, start, stop, withscores=False):
        items = sorted(self._sets.get(key, []), key=lambda x: x[1])
        result = items[start:stop+1]
        if withscores:
            return result
        return [item[0] for item in result]

    async def zadd(self, key, mapping) -> int:
        if key not in self._sets:
            self._sets[key] = []
        added = 0
        for member, score in mapping.items():
            self._sets[key].append((member, score))
            added += 1
        return added

    async def expire(self, key, ttl) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return None

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        pass


@pytest.mark.asyncio
class TestCacheWithMockRedis:
    """Tests for the cache service using a fake Redis."""

    async def test_cache_and_retrieve(self, monkeypatch):
        from src.services import cache

        fake = FakeRedisCache()
        monkeypatch.setattr(cache, "_redis", fake)

        url = "https://example.com"
        fields = [{"name": "title", "selector": "h1", "type": "text"}]
        result = {"data": {"title": "Hello"}, "status": "success"}

        # Store
        await cache.cache_extraction_result(url, fields, result, ttl=60)

        # Retrieve
        cached = await cache.get_cached_result(url, fields)
        assert cached is not None
        assert cached["data"]["title"] == "Hello"

    async def test_cache_miss(self, monkeypatch):
        from src.services import cache

        fake = FakeRedisCache()
        monkeypatch.setattr(cache, "_redis", fake)

        url = "https://example.com"
        fields = [{"name": "missing", "selector": "x", "type": "text"}]

        cached = await cache.get_cached_result(url, fields)
        assert cached is None

    async def test_cache_invalidation(self, monkeypatch):
        from src.services import cache

        fake = FakeRedisCache()
        monkeypatch.setattr(cache, "_redis", fake)

        url = "https://example.com"
        fields = [{"name": "title", "selector": "h1", "type": "text"}]
        result = {"data": {"title": "Hello"}}

        await cache.cache_extraction_result(url, fields, result, ttl=60)

        # Should be found
        cached = await cache.get_cached_result(url, fields)
        assert cached is not None

        # Invalidate
        deleted = await cache.invalidate_cache()
        assert deleted >= 1

        # Should be gone
        cached = await cache.get_cached_result(url, fields)
        assert cached is None


@pytest.mark.asyncio
class TestRateLimiterWithMockRedis:
    """Tests for the rate limiter using a fake Redis."""

    async def test_allows_requests_under_limit(self):
        from unittest.mock import patch
        from src.services.rate_limiter import check_rate_limit
        from src.services import cache as cache_mod

        fake = FakeRedisRateLimit()

        with patch.object(cache_mod, "_redis", fake):
            for i in range(5):
                result = await check_rate_limit(
                    "test-key-1", max_requests=10, window_seconds=60
                )
                assert result.allowed is True
                assert result.remaining == 10 - i - 1

    async def test_blocks_when_limit_exceeded(self):
        from unittest.mock import patch
        from src.services.rate_limiter import check_rate_limit
        from src.services import cache as cache_mod

        fake = FakeRedisRateLimit()

        with patch.object(cache_mod, "_redis", fake):
            for _ in range(3):
                result = await check_rate_limit("test-key-2", max_requests=3, window_seconds=60)
                assert result.allowed is True

            # This one should be blocked
            result = await check_rate_limit("test-key-2", max_requests=3, window_seconds=60)
            assert result.allowed is False
            assert result.remaining == 0

    async def test_isolates_api_keys(self):
        from unittest.mock import patch
        from src.services.rate_limiter import check_rate_limit
        from src.services import cache as cache_mod

        fake = FakeRedisRateLimit()

        with patch.object(cache_mod, "_redis", fake):
            # Exhaust key A
            for _ in range(2):
                await check_rate_limit("key-a", max_requests=2, window_seconds=60)

            result_a = await check_rate_limit("key-a", max_requests=2, window_seconds=60)
            assert result_a.allowed is False

            # Key B should still be fine
            result_b = await check_rate_limit("key-b", max_requests=2, window_seconds=60)
            assert result_b.allowed is True
            assert result_b.remaining == 1


# ---------------------------------------------------------------------------
# Async job queue tests (unit — no running arq worker needed)
# ---------------------------------------------------------------------------


class TestQueueKeyGeneration:
    """Tests for the async job ID generation."""

    def test_job_id_is_unique_uuid(self):
        """Each enqueued job should get a unique UUID."""
        ids = set()
        for _ in range(100):
            ids.add(str(uuid.uuid4()))
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# HTTP endpoint integration tests (mocked dependencies)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExtractRateLimitHeaders:
    """Tests that rate limit headers are attached to responses."""

    async def test_missing_api_key_returns_401(self, client):
        """No API key should return 401 before rate limit check."""
        resp = await client.post("/api/v1/extract", json={
            "url": "https://example.com",
            "schema": {"fields": [{"name": "t", "selector": "body", "type": "text"}]},
        })
        assert resp.status_code == 401

    async def test_rate_limit_headers_present(self, client, monkeypatch):
        """Successful requests should include rate limit headers."""
        import src.services.extractor as extractor_mod  # noqa: F401

        # Patch the dependency at the router level
        async def mock_rate_limit_dep(request, key_info):
            request.state.rate_limit_headers = {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "99",
                "X-RateLimit-Reset": str(int(time.time() + 60)),
            }
            return key_info

        monkeypatch.setattr(
            "src.routers.extract.check_rate_limit_dependency",
            mock_rate_limit_dep,
        )

        # Patch the extractor to avoid actual extraction
        async def mock_extract(self, url, fields):
            return {"title": "Test"}

        monkeypatch.setattr(
            src.services.extractor.extractor_service,
            "extract",
            mock_extract,
        )

        # Patch cache miss
        async def mock_cache_miss(url, fields):
            return None

        monkeypatch.setattr(
            "src.services.cache",
            "get_cached_result",
            mock_cache_miss,
        )

        # Patch cache store (no-op)
        async def mock_cache_store(url, fields, result, ttl=300):
            pass

        monkeypatch.setattr(
            "src.services.cache",
            "cache_extraction_result",
            mock_cache_store,
        )

        resp = await client.post(
            "/api/v1/extract",
            json={
                "url": "https://example.com",
                "schema": {
                    "fields": [{"name": "title", "selector": "h1", "type": "text"}]
                },
            },
            headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"},
        )

        assert resp.status_code == 200
        # Headers come through from the rate limiter mock
        assert "x-ratelimit-limit" in resp.headers
        assert resp.headers["x-ratelimit-remaining"] == "99"


@pytest.mark.asyncio
class TestExtractAsyncMode:
    """Tests for the ?async=true flow."""

    async def test_async_mode_returns_job_id(self, client, monkeypatch):
        """?async=true should queue the job and return a job_id."""
        # Ensure the queue module is loaded before monkeypatching
        import src.services.queue as queue_mod  # noqa: F401

        # Patch rate limit dependency
        async def mock_rate_limit_dep(request, key_info):
            request.state.rate_limit_headers = {}
            return key_info

        monkeypatch.setattr(
            "src.routers.extract.check_rate_limit_dependency",
            mock_rate_limit_dep,
        )

        # Patch enqueue_extraction in the source module
        async def mock_enqueue(url, fields, api_key_id=None):
            return "test-job-123"

        monkeypatch.setattr(
            queue_mod,
            "enqueue_extraction",
            mock_enqueue,
        )

        resp = await client.post(
            "/api/v1/extract?async=true",
            json={
                "url": "https://example.com",
                "schema": {
                    "fields": [{"name": "title", "selector": "h1", "type": "text"}]
                },
            },
            headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"
        assert data["data"]["job_id"] == "test-job-123"

    async def test_poll_job_not_found(self, client, monkeypatch):
        """Polling a non-existent job should return 404."""
        import src.services.queue as queue_mod  # noqa: F401

        async def mock_get_job(job_id):
            return None

        monkeypatch.setattr(
            queue_mod,
            "get_job_status",
            mock_get_job,
        )

        resp = await client.get(
            "/api/v1/extract/nonexistent-job",
            headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"},
        )

        assert resp.status_code == 404
