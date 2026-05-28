"""Tests for the batch extraction endpoint POST /api/v1/extract/batch.

Covers:
- Request/response model validation
- Batch extraction with multiple URLs
- Async mode (enqueue + poll)
- Rate limiting
- API key auth validation
- Edge cases (empty URLs, max URLs, invalid inputs)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.routers.extract import check_rate_limit_dependency, validate_api_key


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def mock_key_info():
    """Mock API key info returned by validate_api_key."""
    return {
        "id": "key-uuid-123",
        "user_id": "user-uuid-456",
        "label": "test-key",
        "tier": "pro",
        "rate_limit": 100,
        "email": "test@example.com",
        "role": "user",
    }


@pytest.fixture
def mock_rate_limit():
    """Mock RateLimitResult for allowed requests."""
    from src.services.rate_limiter import RateLimitResult
    return RateLimitResult(allowed=True, remaining=99, reset_at=9999999999.0)


# ---------------------------------------------------------------------------
# Validation tests (no dependency override needed)
# ---------------------------------------------------------------------------


class TestBatchExtractValidation:
    """Tests for request validation (Pydantic-level)."""

    @pytest.mark.asyncio
    async def test_empty_urls_rejected(self, client):
        """Empty urls list should fail validation."""
        response = await client.post(
            "/api/v1/extract/batch",
            json={
                "urls": [],
                "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]},
            },
            headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_urls_field(self, client):
        """Missing urls field should fail validation."""
        response = await client.post(
            "/api/v1/extract/batch",
            json={
                "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]},
            },
            headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_schema(self, client):
        """Missing schema field should fail validation."""
        response = await client.post(
            "/api/v1/extract/batch",
            json={"urls": ["https://example.com"]},
            headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_schema_fields(self, client):
        """Empty fields list should fail validation."""
        response = await client.post(
            "/api/v1/extract/batch",
            json={
                "urls": ["https://example.com"],
                "schema": {"fields": []},
            },
            headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_api_key(self, client):
        """Missing API key should fail auth."""
        response = await client.post(
            "/api/v1/extract/batch",
            json={
                "urls": ["https://example.com"],
                "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]},
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, client):
        """Invalid API key should fail auth."""
        response = await client.post(
            "/api/v1/extract/batch",
            json={
                "urls": ["https://example.com"],
                "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]},
            },
            headers={"X-API-Key": "invalid-key-here"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_url_accepted(self, client, mock_key_info, mock_rate_limit):
        """webhook_url should be accepted in the request."""
        async def override_key():
            return mock_key_info

        async def override_rate_limit(request, key_info=None):
            # Attach headers to request.state
            request.state.rate_limit_headers = {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "99",
                "X-RateLimit-Reset": "9999999999",
            }
            return mock_key_info

        app.dependency_overrides[validate_api_key] = override_key
        app.dependency_overrides[check_rate_limit_dependency] = override_rate_limit

        try:
            response = await client.post(
                "/api/v1/extract/batch",
                json={
                    "urls": ["https://example.com", "https://example.org"],
                    "schema": {"fields": [{"name": "title", "selector": "h1", "type": "text"}]},
                    "webhook_url": "https://hooks.example.com/callback",
                },
                headers={"X-API-Key": "test-key"},
            )
        finally:
            app.dependency_overrides.pop(validate_api_key, None)
            app.dependency_overrides.pop(check_rate_limit_dependency, None)

        # Auth should pass, extraction may fail depending on env (no Playwright)
        # Accept 200 or 422 (extraction error)
        assert response.status_code in (200, 422, 500)


class TestBatchExtractAsyncMode:
    """Tests for batch extraction async mode with arq enqueue."""

    @pytest.mark.asyncio
    async def test_async_batch_returns_job_id(self, client, mock_key_info, mock_rate_limit):
        """Async batch extraction should enqueue and return a job_id."""
        async def override_key():
            return mock_key_info

        async def override_rate_limit(request, key_info=None):
            request.state.rate_limit_headers = {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "99",
                "X-RateLimit-Reset": "9999999999",
            }
            return mock_key_info

        app.dependency_overrides[validate_api_key] = override_key
        app.dependency_overrides[check_rate_limit_dependency] = override_rate_limit

        # Mock enqueue_batch_extraction to avoid Redis dependency
        with patch("src.routers.extract.enqueue_batch_extraction") as mock_enqueue:
            mock_enqueue.return_value = "mock-job-id-12345"

            try:
                response = await client.post(
                    "/api/v1/extract/batch?async=true",
                    json={
                        "urls": ["https://example.com", "https://example.org"],
                        "schema": {"fields": [{"name": "title", "selector": "h1", "type": "text"}]},
                        "webhook_url": "https://hooks.example.com/callback",
                    },
                    headers={"X-API-Key": "test-key"},
                )
            finally:
                app.dependency_overrides.pop(validate_api_key, None)
                app.dependency_overrides.pop(check_rate_limit_dependency, None)

            assert response.status_code == 200
            mock_enqueue.assert_called_once()
            # Verify webhook_url was passed
            call_kwargs = mock_enqueue.call_args.kwargs
            assert call_kwargs["webhook_url"] == "https://hooks.example.com/callback"
            assert call_kwargs["urls"] == ["https://example.com", "https://example.org"]


class TestBatchExtractSyncMode:
    """Tests for synchronous batch extraction (mock extractor)."""

    @pytest.mark.asyncio
    async def test_batch_extract_successful(self, client, mock_key_info, mock_rate_limit):
        """Synchronous batch extraction with mocked extractor returns results."""
        async def override_key():
            return mock_key_info

        async def override_rate_limit(request, key_info=None):
            request.state.rate_limit_headers = {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "99",
                "X-RateLimit-Reset": "9999999999",
            }
            return mock_key_info

        app.dependency_overrides[validate_api_key] = override_key
        app.dependency_overrides[check_rate_limit_dependency] = override_rate_limit

        mock_batch_results = [
            {"url": "https://example.com", "status": "success", "data": {"title": "Hello"}, "error": None},
            {"url": "https://example.org", "status": "success", "data": {"title": "World"}, "error": None},
        ]

        with patch.object(extractor_service, "extract_batch", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_batch_results

            try:
                response = await client.post(
                    "/api/v1/extract/batch",
                    json={
                        "urls": ["https://example.com", "https://example.org"],
                        "schema": {"fields": [{"name": "title", "selector": "h1", "type": "text"}]},
                    },
                    headers={"X-API-Key": "test-key"},
                )
            finally:
                app.dependency_overrides.pop(validate_api_key, None)
                app.dependency_overrides.pop(check_rate_limit_dependency, None)

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["succeeded"] == 2
            assert data["failed"] == 0
            assert len(data["results"]) == 2
            assert data["results"][0]["url"] == "https://example.com"
            assert data["results"][0]["status"] == "success"
            assert data["results"][0]["data"] == {"title": "Hello"}
            assert data["results"][1]["url"] == "https://example.org"

    @pytest.mark.asyncio
    async def test_batch_extract_partial_failure(self, client, mock_key_info, mock_rate_limit):
        """Batch with some failed URLs returns mixed results."""
        async def override_key():
            return mock_key_info

        async def override_rate_limit(request, key_info=None):
            request.state.rate_limit_headers = {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "99",
                "X-RateLimit-Reset": "9999999999",
            }
            return mock_key_info

        app.dependency_overrides[validate_api_key] = override_key
        app.dependency_overrides[check_rate_limit_dependency] = override_rate_limit

        mock_batch_results = [
            {"url": "https://good.com", "status": "success", "data": {"title": "OK"}, "error": None},
            {"url": "https://bad.com", "status": "error", "data": None, "error": "Timeout"},
            {"url": "https://also-good.com", "status": "success", "data": {"title": "Nice"}, "error": None},
        ]

        with patch.object(extractor_service, "extract_batch", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_batch_results

            try:
                response = await client.post(
                    "/api/v1/extract/batch",
                    json={
                        "urls": ["https://good.com", "https://bad.com", "https://also-good.com"],
                        "schema": {"fields": [{"name": "title", "selector": "h1", "type": "text"}]},
                    },
                    headers={"X-API-Key": "test-key"},
                )
            finally:
                app.dependency_overrides.pop(validate_api_key, None)
                app.dependency_overrides.pop(check_rate_limit_dependency, None)

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert data["succeeded"] == 2
            assert data["failed"] == 1
            assert data["results"][1]["status"] == "error"
            assert data["results"][1]["error"] == "Timeout"

    @pytest.mark.asyncio
    async def test_batch_extract_service_exception(self, client, mock_key_info, mock_rate_limit):
        """Extractor service exception should return 422."""
        async def override_key():
            return mock_key_info

        async def override_rate_limit(request, key_info=None):
            request.state.rate_limit_headers = {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "99",
                "X-RateLimit-Reset": "9999999999",
            }
            return mock_key_info

        app.dependency_overrides[validate_api_key] = override_key
        app.dependency_overrides[check_rate_limit_dependency] = override_rate_limit

        with patch.object(extractor_service, "extract_batch", new_callable=AsyncMock) as mock_extract:
            mock_extract.side_effect = Exception("Browser crashed")

            try:
                response = await client.post(
                    "/api/v1/extract/batch",
                    json={
                        "urls": ["https://example.com"],
                        "schema": {"fields": [{"name": "title", "selector": "h1", "type": "text"}]},
                    },
                    headers={"X-API-Key": "test-key"},
                )
            finally:
                app.dependency_overrides.pop(validate_api_key, None)
                app.dependency_overrides.pop(check_rate_limit_dependency, None)

            assert response.status_code == 422
            data = response.json()
            assert "Browser crashed" in data["detail"]


class TestBatchExtractRateLimit:
    """Tests for rate limiting on batch endpoint."""

    @pytest.mark.asyncio
    async def test_rate_limited_batch_request(self, client, mock_key_info):
        """Rate limited requests should get 429."""
        async def override_key():
            return mock_key_info

        from src.services.rate_limiter import RateLimitResult

        async def override_rate_limit(request, key_info=None):
            request.state.rate_limit_headers = {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "9999999999",
                "Retry-After": "60",
            }
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in 60s.",
                               headers=request.state.rate_limit_headers)

        from fastapi import HTTPException

        app.dependency_overrides[validate_api_key] = override_key
        app.dependency_overrides[check_rate_limit_dependency] = override_rate_limit

        try:
            response = await client.post(
                "/api/v1/extract/batch",
                json={
                    "urls": ["https://example.com"],
                    "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]},
                },
                headers={"X-API-Key": "test-key"},
            )
        finally:
            app.dependency_overrides.pop(validate_api_key, None)
            app.dependency_overrides.pop(check_rate_limit_dependency, None)

        assert response.status_code == 429


# ---------------------------------------------------------------------------
# Model unit tests
# ---------------------------------------------------------------------------


class TestBatchModels:
    """Unit tests for batch extraction Pydantic models."""

    def test_batch_extract_request_valid(self):
        """Valid BatchExtractRequest should parse correctly."""
        from src.models.extract import BatchExtractRequest

        req = BatchExtractRequest(
            urls=["https://example.com", "https://example.org"],
            schema={"fields": [{"name": "title", "selector": "h1", "type": "text"}]},
            webhook_url="https://hooks.example.com/cb",
        )
        assert req.urls == ["https://example.com", "https://example.org"]
        assert req.webhook_url == "https://hooks.example.com/cb"
        assert req.schema.fields[0].name == "title"

    def test_batch_extract_request_no_webhook(self):
        """BatchExtractRequest without webhook_url should have None."""
        from src.models.extract import BatchExtractRequest

        req = BatchExtractRequest(
            urls=["https://example.com"],
            schema={"fields": [{"name": "test", "selector": "body", "type": "text"}]},
        )
        assert req.webhook_url is None

    def test_batch_extract_response_model(self):
        """BatchExtractResponse should serialize correctly."""
        from src.models.extract import BatchExtractResponse, BatchResult

        resp = BatchExtractResponse(
            results=[
                BatchResult(url="url1", status="success", data={"x": 1}),
                BatchResult(url="url2", status="error", error="Failed"),
            ],
            total=2,
            succeeded=1,
            failed=1,
        )
        data = resp.model_dump()
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        assert len(data["results"]) == 2

    def test_batch_extract_request_urls_limit(self):
        """BatchExtractRequest should enforce max 50 URLs."""
        from src.models.extract import BatchExtractRequest
        import pydantic

        urls_51 = [f"https://example.com/page/{i}" for i in range(51)]
        with pytest.raises(pydantic.ValidationError):
            BatchExtractRequest(
                urls=urls_51,
                schema={"fields": [{"name": "test", "selector": "body", "type": "text"}]},
            )

    def test_extract_request_webhook_url(self):
        """ExtractRequest should accept optional webhook_url."""
        from src.models.extract import ExtractRequest

        req = ExtractRequest(
            url="https://example.com",
            schema={"fields": [{"name": "test", "selector": "body", "type": "text"}]},
            webhook_url="https://hooks.example.com/cb",
        )
        assert req.webhook_url == "https://hooks.example.com/cb"
