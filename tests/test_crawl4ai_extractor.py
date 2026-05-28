"""Tests for Crawl4AI-based extraction service.

Tests the ExtractorService with Crawl4AI's JsonCssExtractionStrategy
and various field types. Uses a local HTML file served via a simple HTTP server
to avoid external dependencies.
"""

from __future__ import annotations

import asyncio
import base64
import http.server
import json
import os
import threading
from pathlib import Path

import pytest

from src.services.extractor import ExtractionError, ExtractorService


# ---------------------------------------------------------------------------
# HTML fixture served on localhost for testing
# ---------------------------------------------------------------------------

TEST_HTML = """<!DOCTYPE html>
<html lang="en">
<head><title>Test Page</title></head>
<body>
    <div class="container">
        <h1 class="title">Hello World</h1>
        <p class="subtitle">A test paragraph</p>
        <a class="link" href="https://example.com">Example Link</a>
        <span class="price">$19.99</span>
        <ul class="items">
            <li class="item">Apple</li>
            <li class="item">Banana</li>
            <li class="item">Cherry</li>
        </ul>
        <div class="empty-section"></div>
        <div class="nested">
            <span class="nested-text">Deep Value</span>
        </div>
    </div>
</body>
</html>
"""


class _TestServer:
    """Tiny HTTP server for serving test HTML."""

    def __init__(self) -> None:
        self.port: int = 0
        self._thread: threading.Thread | None = None
        self._server: http.server.HTTPServer | None = None

    def start(self) -> str:
        """Start the server and return the base URL."""
        self._server = http.server.HTTPServer(
            ("127.0.0.1", 0),
            lambda *args: _Handler(TEST_HTML, *args),
        )
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None


class _Handler(http.server.BaseHTTPRequestHandler):
    """Handler that always returns the test HTML."""

    def __init__(self, html: str, *args) -> None:
        self._html = html
        super().__init__(*args)

    def do_GET(self) -> None:
        content = self._html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args) -> None:
        pass  # Silence logs


@pytest.fixture(scope="module")
def test_server():
    """Fixture that starts/stops the test HTTP server."""
    server = _TestServer()
    url = server.start()
    yield url
    server.stop()


@pytest.fixture(scope="module")
def event_loop():
    """Create a module-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Shared extractor service for the module
# ---------------------------------------------------------------------------

_extractor: ExtractorService | None = None


async def _get_extractor() -> ExtractorService:
    global _extractor
    if _extractor is None:
        _extractor = ExtractorService()
    return _extractor


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCrawl4AIExtractor:
    """Integration tests for Crawl4AI-based ExtractorService."""

    @pytest.mark.asyncio
    async def test_extract_text_field(self, test_server: str) -> None:
        """Extract a text field via CSS selector."""
        svc = await _get_extractor()
        fields = [
            {"name": "title", "selector": "h1.title", "type": "text"},
        ]
        result = await svc.extract(test_server, fields)
        assert result["title"] == "Hello World"

    @pytest.mark.asyncio
    async def test_extract_html_field(self, test_server: str) -> None:
        """Extract inner HTML of an element."""
        svc = await _get_extractor()
        fields = [
            {"name": "link_html", "selector": "a.link", "type": "html"},
        ]
        result = await svc.extract(test_server, fields)
        assert "Example Link" in result["link_html"]
        assert "<a" in result["link_html"]

    @pytest.mark.asyncio
    async def test_extract_attribute_field(self, test_server: str) -> None:
        """Extract an attribute from an element."""
        svc = await _get_extractor()
        fields = [
            {
                "name": "link_href",
                "selector": "a.link",
                "type": "attribute",
                "attribute": "href",
            },
        ]
        result = await svc.extract(test_server, fields)
        assert result["link_href"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_extract_multiple_fields(self, test_server: str) -> None:
        """Extract multiple fields in one request."""
        svc = await _get_extractor()
        fields = [
            {"name": "title", "selector": "h1.title", "type": "text"},
            {"name": "subtitle", "selector": "p.subtitle", "type": "text"},
            {"name": "price", "selector": "span.price", "type": "text"},
        ]
        result = await svc.extract(test_server, fields)
        assert result["title"] == "Hello World"
        assert result["subtitle"] == "A test paragraph"
        assert result["price"] == "$19.99"

    @pytest.mark.asyncio
    async def test_extract_markdown(self, test_server: str) -> None:
        """Extract markdown representation of the page."""
        svc = await _get_extractor()
        fields = [
            {"name": "md", "selector": "", "type": "markdown"},
        ]
        result = await svc.extract(test_server, fields)
        assert "md" in result
        assert "Hello World" in result["md"]
        assert "Example Link" in result["md"]

    @pytest.mark.asyncio
    async def test_extract_screenshot(self, test_server: str) -> None:
        """Extract a screenshot of the page."""
        svc = await _get_extractor()
        fields = [
            {"name": "shot", "selector": "", "type": "screenshot"},
        ]
        result = await svc.extract(test_server, fields)
        assert "shot" in result
        # Screenshot should be a base64-encoded string (or empty if disabled)
        assert isinstance(result["shot"], str)

    @pytest.mark.asyncio
    async def test_extract_combined_fields(self, test_server: str) -> None:
        """Extract CSS fields + markdown together."""
        svc = await _get_extractor()
        fields = [
            {"name": "title", "selector": "h1.title", "type": "text"},
            {"name": "md", "selector": "", "type": "markdown"},
        ]
        result = await svc.extract(test_server, fields)
        assert result["title"] == "Hello World"
        assert "Hello World" in result["md"]

    @pytest.mark.asyncio
    async def test_extract_exists_field(self, test_server: str) -> None:
        """Extract 'exists' type — returns boolean."""
        svc = await _get_extractor()
        fields = [
            {"name": "has_title", "selector": "h1.title", "type": "exists"},
            {"name": "has_nothing", "selector": "div.nonexistent", "type": "exists"},
        ]
        result = await svc.extract(test_server, fields)
        assert result["has_title"] is True
        assert result["has_nothing"] is False

    @pytest.mark.asyncio
    async def test_extract_invalid_url(self) -> None:
        """Extraction from an invalid URL should raise ExtractionError."""
        svc = await _get_extractor()
        fields = [
            {"name": "title", "selector": "h1", "type": "text"},
        ]
        with pytest.raises(ExtractionError):
            await svc.extract("http://invalid-host-that-does-not-exist.local", fields)


class TestExtractorServiceInternals:
    """Unit tests for internal helpers."""

    def test_parse_css_results_single_item(self) -> None:
        """Parse a single-item CSS result list."""
        svc = ExtractorService()
        fields = [
            {"name": "a", "selector": "h1", "type": "text"},
            {"name": "b", "selector": "p", "type": "text"},
        ]
        css_data = [{"a": "Hello", "b": "World"}]
        result = svc._parse_css_results(fields, css_data)
        assert result == {"a": "Hello", "b": "World"}

    def test_parse_css_results_dict(self) -> None:
        """Parse a dict CSS result."""
        svc = ExtractorService()
        fields = [{"name": "x", "selector": "span", "type": "text"}]
        result = svc._parse_css_results(fields, {"x": "val"})
        assert result == {"x": "val"}

    def test_parse_css_results_exists_true(self) -> None:
        """Parse exists=True when value is truthy."""
        svc = ExtractorService()
        fields = [{"name": "present", "selector": "div", "type": "exists"}]
        result = svc._parse_css_results(fields, [{"present": "some text"}])
        assert result == {"present": True}

    def test_parse_css_results_exists_false(self) -> None:
        """Parse exists=False when value is empty/None."""
        svc = ExtractorService()
        fields = [{"name": "missing", "selector": ".none", "type": "exists"}]
        result = svc._parse_css_results(fields, [{"missing": ""}])
        assert result == {"missing": False}

    def test_parse_ai_results_dict(self) -> None:
        """Parse AI results from a dict."""
        svc = ExtractorService()
        fields = [{"name": "answer", "selector": "", "type": "ai"}]
        result = svc._parse_ai_results(fields, {"answer": "42"})
        assert result == {"answer": "42"}

    def test_parse_ai_results_list(self) -> None:
        """Parse AI results from a list."""
        svc = ExtractorService()
        fields = [{"name": "answer", "selector": "", "type": "ai"}]
        result = svc._parse_ai_results(fields, [{"answer": "42"}])
        assert result == {"answer": "42"}

    def test_build_css_strategy(self) -> None:
        """Build JsonCssExtractionStrategy schema from fields."""
        svc = ExtractorService()
        fields = [
            {"name": "title", "selector": "h1", "type": "text"},
            {"name": "link", "selector": "a", "type": "attribute", "attribute": "href"},
        ]
        strategy = svc._build_css_strategy(fields)
        assert strategy.schema["name"] == "Extraction"
        assert strategy.schema["baseSelector"] == "body"
        assert len(strategy.schema["fields"]) == 2
        assert strategy.schema["fields"][0]["name"] == "title"
        assert strategy.schema["fields"][1]["type"] == "attribute"

    def test_build_ai_strategy(self) -> None:
        """Build LLMExtractionStrategy from AI field definitions."""
        svc = ExtractorService()
        fields = [
            {
                "name": "summary",
                "selector": "",
                "type": "ai",
                "instruction": "Summarize the page content",
            },
        ]
        strategy = svc._build_ai_strategy(fields)
        assert strategy.instruction is not None
        assert "summary" in strategy.instruction
        assert strategy.extract_type == "schema"
        assert strategy.force_json_response is True
