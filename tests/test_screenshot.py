"""Tests for P2-4: Screenshot extraction endpoint and service.

Tests the ScreenshotRequest model, the extract_screenshot() service method,
and the POST /api/v1/extract/screenshot endpoint.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import Depends

from src.config import settings
from src.models.extract import ScreenshotData, ScreenshotRequest, ScreenshotResponse
from src.services.extractor import ExtractorService


# A minimal valid base64 PNG
MINI_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU"
    "5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestScreenshotModels:
    """Test P2-4 request/response models."""

    def test_minimal_request(self) -> None:
        """Validate a minimal screenshot request."""
        req = ScreenshotRequest(url="https://example.com")
        assert req.url == "https://example.com"
        assert req.full_page is False
        assert req.selector is None

    def test_full_page_request(self) -> None:
        """Full-page screenshot with selector."""
        req = ScreenshotRequest(
            url="https://example.com",
            full_page=True,
            selector=".main-content",
        )
        assert req.full_page is True
        assert req.selector == ".main-content"

    def test_screenshot_data_model(self) -> None:
        """ScreenshotData model serialization."""
        data = ScreenshotData(screenshot=MINI_PNG_B64, format="png")
        d = data.model_dump()
        assert d["screenshot"] == MINI_PNG_B64
        assert d["format"] == "png"

    def test_screenshot_response_model(self) -> None:
        """ScreenshotResponse model serialization."""
        from src.models.extract import ExtractMetadata

        resp = ScreenshotResponse(
            status="success",
            data=ScreenshotData(screenshot=MINI_PNG_B64, format="png"),
            metadata=ExtractMetadata(
                url="https://example.com",
                duration_ms=1200,
                timestamp="2024-01-01T00:00:00Z",
            ),
        )
        d = resp.model_dump()
        assert d["status"] == "success"
        assert d["data"]["screenshot"] == MINI_PNG_B64
        assert d["data"]["format"] == "png"
        assert d["metadata"]["duration_ms"] == 1200


# ---------------------------------------------------------------------------
# ExtractorService screenshot tests
# ---------------------------------------------------------------------------


class TestExtractorServiceScreenshot:
    """Unit tests for ExtractorService.extract_screenshot() — mocks Crawl4AI."""

    @pytest.mark.asyncio
    async def test_extract_screenshot_success(self) -> None:
        """extract_screenshot() returns base64 PNG and format."""
        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.screenshot = MINI_PNG_B64

        mock_crawler = MagicMock()
        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            result = await svc.extract_screenshot(url="https://example.com")

        assert result["screenshot"] == MINI_PNG_B64
        assert result["format"] == "png"
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_extract_screenshot_full_page(self) -> None:
        """Full-page flag is passed through."""
        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.screenshot = MINI_PNG_B64

        mock_crawler = MagicMock()
        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            result = await svc.extract_screenshot(
                url="https://example.com",
                full_page=True,
            )

        assert result["screenshot"] == MINI_PNG_B64
        assert result["format"] == "png"

    @pytest.mark.asyncio
    async def test_extract_screenshot_with_selector(self) -> None:
        """CSS selector is set on run config."""
        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.screenshot = MINI_PNG_B64

        mock_crawler = MagicMock()
        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            result = await svc.extract_screenshot(
                url="https://example.com",
                selector=".hero-section",
            )

        assert result["screenshot"] == MINI_PNG_B64

    @pytest.mark.asyncio
    async def test_extract_screenshot_failure_raises_error(self) -> None:
        """Failed screenshot should raise ExtractionError."""
        from src.services.extractor import ExtractionError

        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = False
        mock_crawl_result.error_message = "Timeout"

        mock_crawler = MagicMock()
        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            with pytest.raises(ExtractionError, match="Timeout"):
                await svc.extract_screenshot(url="https://example.com")

    @pytest.mark.asyncio
    async def test_extract_screenshot_empty_result(self) -> None:
        """Empty screenshot result returns empty string."""
        svc = ExtractorService()

        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.screenshot = ""

        mock_crawler = MagicMock()
        mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)

        with patch.object(svc, "_get_crawler", return_value=mock_crawler):
            result = await svc.extract_screenshot(url="https://example.com")

        assert result["screenshot"] == ""
        assert result["format"] == "png"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def _make_key_info():
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


class TestScreenshotEndpoint:
    """Integration-style tests for POST /api/v1/extract/screenshot."""

    HEADERS = {
        "X-API-Key": "test-key",
        "Content-Type": "application/json",
    }

    @pytest.mark.anyio
    async def test_missing_api_key_returns_401(self):
        """No API key → 401."""
        from src.main import app
        app.dependency_overrides.clear()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post("/api/v1/extract/screenshot", json={
                "url": "https://example.com",
            })
            assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_missing_url_returns_422(self, client: AsyncClient):
        """Missing URL → 422."""
        resp = await client.post(
            "/api/v1/extract/screenshot", json={}, headers=self.HEADERS,
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_full_page_flag_accepted(self, client: AsyncClient):
        """Full-page flag passes validation."""
        body = {"url": "https://example.com", "full_page": True}
        resp = await client.post(
            "/api/v1/extract/screenshot", json=body, headers=self.HEADERS,
        )
        assert resp.status_code != 422

    @pytest.mark.anyio
    async def test_selector_accepted(self, client: AsyncClient):
        """CSS selector passes validation."""
        body = {"url": "https://example.com", "selector": ".content"}
        resp = await client.post(
            "/api/v1/extract/screenshot", json=body, headers=self.HEADERS,
        )
        assert resp.status_code != 422

    @pytest.mark.anyio
    async def test_combined_options_accepted(self, client: AsyncClient):
        """Full page + selector combination passes validation."""
        body = {
            "url": "https://example.com",
            "full_page": True,
            "selector": "#main",
        }
        resp = await client.post(
            "/api/v1/extract/screenshot", json=body, headers=self.HEADERS,
        )
        assert resp.status_code != 422
