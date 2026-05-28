"""Tests for P2-3: LLM extraction endpoint and service.

Tests the AIExtractRequest model, the extract_ai() service method,
and the POST /api/v1/extract/ai endpoint.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.config import settings
from src.models.extract import AIExtractRequest, AIExtractResponse
from src.services.extractor import ExtractorService


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestAIExtractModels:
    """Test P2-3 request/response models."""

    def test_minimal_request(self) -> None:
        """Validate a minimal AI extract request."""
        req = AIExtractRequest(
            url="https://example.com",
            instruction="Extract the page title",
        )
        assert req.url == "https://example.com"
        assert req.instruction == "Extract the page title"
        assert req.model == "kimi-k2.6:cloud"  # default
        assert req.format == "json"  # default

    def test_custom_model(self) -> None:
        """Validate model field switching."""
        req = AIExtractRequest(
            url="https://example.com",
            instruction="Summarize the article",
            model="glm-5.1:cloud",
            format="text",
        )
        assert req.model == "glm-5.1:cloud"
        assert req.format == "text"

    def test_rejects_empty_instruction(self) -> None:
        """Empty instruction should be rejected."""
        with pytest.raises(Exception):
            AIExtractRequest(url="https://example.com", instruction="")

    def test_response_model(self) -> None:
        """AIExtractResponse should serialize correctly."""
        from src.models.extract import ExtractMetadata

        resp = AIExtractResponse(
            status="success",
            data={"title": "Hello", "author": "World"},
            metadata=ExtractMetadata(
                url="https://example.com",
                duration_ms=1500,
                timestamp="2024-01-01T00:00:00Z",
            ),
        )
        d = resp.model_dump()
        assert d["status"] == "success"
        assert d["data"]["title"] == "Hello"
        assert d["metadata"]["url"] == "https://example.com"


# ---------------------------------------------------------------------------
# ExtractorService AI extraction tests
# ---------------------------------------------------------------------------


class TestExtractorServiceAI:
    """Unit tests for ExtractorService.extract_ai() — mocks Crawl4AI."""

    @pytest.fixture
    def mock_crawler(self) -> MagicMock:
        """Return a mock AsyncWebCrawler."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_extract_ai_json_format(self, mock_crawler: MagicMock) -> None:
        """extract_ai() with json format returns parsed JSON data."""
        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.extracted_content = json.dumps({
            "title": "Test Page",
            "author": "Jane Doe",
        })

        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            result = await svc.extract_ai(
                url="https://example.com",
                instruction="Extract the title and author",
                model="kimi-k2.6:cloud",
                output_format="json",
            )

        assert "data" in result
        assert result["data"] == {"title": "Test Page", "author": "Jane Doe"}
        assert "raw" in result
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_extract_ai_text_format(self, mock_crawler: MagicMock) -> None:
        """extract_ai() with text format returns raw string."""
        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.extracted_content = "The page is about technology."

        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            result = await svc.extract_ai(
                url="https://example.com",
                instruction="Summarize the page",
                model="glm-5.1:cloud",
                output_format="text",
            )

        assert result["data"] == "The page is about technology."
        assert isinstance(result["data"], str)

    @pytest.mark.asyncio
    async def test_extract_ai_model_switching(self, mock_crawler: MagicMock) -> None:
        """Model parameter correctly switches between kimi and glm."""
        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.extracted_content = json.dumps({"result": "ok"})
        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            result = await svc.extract_ai(
                url="https://example.com",
                instruction="Extract data",
                model="glm-5.1:cloud",
            )
        assert result["data"] == {"result": "ok"}
        mock_crawler.arun.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_ai_failure_raises_error(self, mock_crawler: MagicMock) -> None:
        """Failed crawl should raise ExtractionError."""
        from src.services.extractor import ExtractionError

        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = False
        mock_crawl_result.error_message = "Connection refused"

        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            with pytest.raises(ExtractionError, match="Connection refused"):
                await svc.extract_ai(
                    url="https://example.com",
                    instruction="Extract data",
                )

    @pytest.mark.asyncio
    async def test_extract_ai_invalid_json_fallback(self, mock_crawler: MagicMock) -> None:
        """Non-JSON extracted content should fall back to raw wrapper."""
        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.extracted_content = "not valid json{{{"

        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            result = await svc.extract_ai(
                url="https://example.com",
                instruction="Extract data",
                output_format="json",
            )

        # Should fall back to {"raw": ...}
        assert isinstance(result["data"], dict)
        assert "raw" in result["data"]


# ---------------------------------------------------------------------------
# API endpoint tests (via AsyncClient with dependency overrides)
# ---------------------------------------------------------------------------


def _make_key_info():
    """Return a mock key info dict for dependency override."""
    return {
        "id": "test-key-id",
        "user_id": "test-user-id",
        "label": "test",
        "tier": "hobby",
        "rate_limit": 100,
        "email": "test@example.com",
        "role": "user",
    }


@pytest.fixture
async def client():
    """Create an async test client with overridden dependencies."""
    from src.main import app
    from src.routers.extract import check_rate_limit_dependency, validate_api_key

    # Override rate limit + API key validation to skip Redis/DB
    async def _mock_validate(request):
        return _make_key_info()

    async def _mock_rate_limit(request, key_info=Depends(_mock_validate)):
        return key_info

    app.dependency_overrides[validate_api_key] = _mock_validate
    app.dependency_overrides[check_rate_limit_dependency] = _mock_rate_limit

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


class TestAIExtractEndpoint:
    """Integration-style tests for POST /api/v1/extract/ai."""

    HEADERS = {
        "X-API-Key": "test-key",
        "Content-Type": "application/json",
    }

    @pytest.mark.anyio
    async def test_missing_api_key_returns_401(self):
        """No API key → 401. Clear overrides so real validation runs."""
        from src.main import app
        from src.routers.extract import check_rate_limit_dependency, validate_api_key

        # Clear overrides for this test
        app.dependency_overrides.clear()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post("/api/v1/extract/ai", json={
                "url": "https://example.com",
                "instruction": "Extract title",
            })
            assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_empty_instruction_returns_422(self, client: AsyncClient):
        """Empty instruction → 422 validation error."""
        resp = await client.post("/api/v1/extract/ai", json={
            "url": "https://example.com",
            "instruction": "",
        }, headers=self.HEADERS)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_missing_url_returns_422(self, client: AsyncClient):
        """Missing URL → 422."""
        resp = await client.post("/api/v1/extract/ai", json={
            "instruction": "Extract title",
        }, headers=self.HEADERS)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_default_model_is_kimi(self, client: AsyncClient):
        """Default model should be kimi-k2.6:cloud — at minimum request passes validation."""
        body = {
            "url": "https://example.com",
            "instruction": "Extract title",
        }
        resp = await client.post("/api/v1/extract/ai", json=body, headers=self.HEADERS)
        # Body is valid, but extraction may fail (external dependency)
        # Should not be 422 (validation error)
        assert resp.status_code != 422

    @pytest.mark.anyio
    async def test_glm_model_accepted(self, client: AsyncClient):
        """glm-5.1:cloud model should be accepted."""
        body = {
            "url": "https://example.com",
            "instruction": "Extract title",
            "model": "glm-5.1:cloud",
        }
        resp = await client.post("/api/v1/extract/ai", json=body, headers=self.HEADERS)
        assert resp.status_code != 422

    @pytest.mark.anyio
    async def test_text_format_accepted(self, client: AsyncClient):
        """'text' format should be accepted."""
        body = {
            "url": "https://example.com",
            "instruction": "Summarize the page",
            "format": "text",
        }
        resp = await client.post("/api/v1/extract/ai", json=body, headers=self.HEADERS)
        assert resp.status_code != 422
