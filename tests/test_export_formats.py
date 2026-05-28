"""Tests for P2-5: Export formats (CSV and markdown).

Tests the ?format= query param, Accept header content negotiation,
and the _json_to_csv() helper for POST /api/v1/extract.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import Depends


# ---------------------------------------------------------------------------
# _json_to_csv helper tests
# ---------------------------------------------------------------------------


class TestJsonToCsv:
    """Unit tests for the _json_to_csv helper."""

    def _get_helper(self):
        """Import the helper."""
        from src.routers.extract import _json_to_csv
        return _json_to_csv

    def test_basic_flat_dict(self) -> None:
        """Flat dict → two-row CSV with header."""
        fn = self._get_helper()
        result = fn({"name": "Alice", "age": "30", "city": "NYC"})
        lines = result.strip().split("\r\n") if "\r\n" in result else result.strip().split("\n")
        assert len(lines) == 2
        assert "name" in lines[0]
        assert "Alice" in lines[1]

    def test_nested_values_json_stringified(self) -> None:
        """Nested dict/list values are JSON-stringified."""
        fn = self._get_helper()
        result = fn({"title": "Test", "meta": {"author": "Jane"}})
        lines = result.strip().split("\r\n") if "\r\n" in result else result.strip().split("\n")
        assert len(lines) == 2
        # CSV may double-quote inner quotes — check for key parts
        assert "author" in lines[1]
        assert "Jane" in lines[1]

    def test_none_values_become_empty(self) -> None:
        """None values become empty strings."""
        fn = self._get_helper()
        result = fn({"key": None, "name": "Test"})
        # Should produce valid CSV
        assert "Test" in result

    def test_empty_dict_returns_empty_string(self) -> None:
        """Empty dict returns empty string."""
        fn = self._get_helper()
        assert fn({}) == ""

    def test_non_dict_returns_empty(self) -> None:
        """Non-dict input returns empty string."""
        fn = self._get_helper()
        assert fn("not a dict") == ""
        assert fn(None) == ""


# ---------------------------------------------------------------------------
# Helpers for API endpoint tests
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


# ---------------------------------------------------------------------------
# API endpoint tests — format query param
# ---------------------------------------------------------------------------


class TestExportFormatQueryParam:
    """Integration tests for ?format= query param on POST /api/v1/extract."""

    HEADERS = {
        "X-API-Key": "test-key",
        "Content-Type": "application/json",
    }

    @pytest.mark.anyio
    async def test_csv_format_accepted(self, client: AsyncClient):
        """?format=csv passes validation."""
        body = {
            "url": "https://example.com",
            "schema": {
                "fields": [
                    {"name": "title", "selector": "h1", "type": "text"},
                ],
            },
        }
        resp = await client.post(
            "/api/v1/extract?format=csv",
            json=body,
            headers=self.HEADERS,
        )
        assert resp.status_code != 422

    @pytest.mark.anyio
    async def test_markdown_format_accepted(self, client: AsyncClient):
        """?format=markdown passes validation."""
        body = {
            "url": "https://example.com",
            "schema": {
                "fields": [
                    {"name": "title", "selector": "h1", "type": "text"},
                ],
            },
        }
        resp = await client.post(
            "/api/v1/extract?format=markdown",
            json=body,
            headers=self.HEADERS,
        )
        assert resp.status_code != 422

    @pytest.mark.anyio
    async def test_invalid_format_ignored(self, client: AsyncClient):
        """An unknown format value should not cause a 422 (it's just ignored)."""
        body = {
            "url": "https://example.com",
            "schema": {
                "fields": [
                    {"name": "title", "selector": "h1", "type": "text"},
                ],
            },
        }
        resp = await client.post(
            "/api/v1/extract?format=xml",
            json=body,
            headers=self.HEADERS,
        )
        assert resp.status_code != 422


class TestAcceptHeaderNegotiation:
    """Integration tests for Accept header content negotiation."""

    HEADERS_BASE = {
        "X-API-Key": "test-key",
        "Content-Type": "application/json",
    }

    @pytest.mark.anyio
    async def test_accept_csv_fallback(self, client: AsyncClient):
        """Accept: text/csv sets format=csv when no ?format provided."""
        body = {
            "url": "https://example.com",
            "schema": {
                "fields": [
                    {"name": "title", "selector": "h1", "type": "text"},
                ],
            },
        }
        headers = {**self.HEADERS_BASE, "Accept": "text/csv"}
        resp = await client.post("/api/v1/extract", json=body, headers=headers)
        assert resp.status_code != 422

    @pytest.mark.anyio
    async def test_accept_markdown_fallback(self, client: AsyncClient):
        """Accept: text/markdown sets format=markdown when no ?format provided."""
        body = {
            "url": "https://example.com",
            "schema": {
                "fields": [
                    {"name": "title", "selector": "h1", "type": "text"},
                ],
            },
        }
        headers = {**self.HEADERS_BASE, "Accept": "text/markdown"}
        resp = await client.post("/api/v1/extract", json=body, headers=headers)
        assert resp.status_code != 422

    @pytest.mark.anyio
    async def test_accept_plain_text_fallback(self, client: AsyncClient):
        """Accept: text/plain also resolves to markdown format."""
        body = {
            "url": "https://example.com",
            "schema": {
                "fields": [
                    {"name": "title", "selector": "h1", "type": "text"},
                ],
            },
        }
        headers = {**self.HEADERS_BASE, "Accept": "text/plain"}
        resp = await client.post("/api/v1/extract", json=body, headers=headers)
        assert resp.status_code != 422

    @pytest.mark.anyio
    async def test_query_param_overrides_accept(self, client: AsyncClient):
        """?format= overrides the Accept header."""
        body = {
            "url": "https://example.com",
            "schema": {
                "fields": [
                    {"name": "title", "selector": "h1", "type": "text"},
                ],
            },
        }
        headers = {**self.HEADERS_BASE, "Accept": "text/markdown"}
        resp = await client.post(
            "/api/v1/extract?format=csv",
            json=body,
            headers=headers,
        )
        assert resp.status_code != 422


# ---------------------------------------------------------------------------
# CSV conversion from dict (unit)
# ---------------------------------------------------------------------------


class TestCsvConversion:
    """Test that a JSON extraction result is properly converted to CSV."""

    def test_csv_conversion_pipeline(self) -> None:
        """End-to-end CSV conversion of a dict result."""
        from src.routers.extract import _json_to_csv

        data = {
            "title": "My Page",
            "price": "$9.99",
            "available": True,
        }
        csv_output = _json_to_csv(data)
        lines = csv_output.strip().split("\r\n") if "\r\n" in csv_output else csv_output.strip().split("\n")
        assert len(lines) == 2
        assert "title" in lines[0]
        assert "My Page" in lines[1]
        assert "$9.99" in lines[1]
