"""Kaf Extract Python SDK.

Usage:
    from kaf_extract import KafExtract

    client = KafExtract(api_key="kaf_xxxx")
    result = client.extract("https://example.com", fields=[
        {"name": "title", "selector": "h1", "type": "text"},
    ])
"""

import asyncio
import base64
import json
import time
from typing import Any, Optional

import httpx

from .models import (
    AIExtractRequest,
    BatchExtractRequest,
    BatchExtractResponse,
    ExtractRequest,
    ExtractResponse,
    ExtractSchema,
    FieldSchema,
    LoginRequest,
    RegisterRequest,
    ScreenshotRequest,
    ScreenshotResponse,
    TokenResponse,
    UserResponse,
    VoucherResponse,
)


class KafExtractError(Exception):
    """Base exception for Kaf Extract client errors."""

    def __init__(self, message: str, status_code: int = 0, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class KafExtract:
    """Client for the Kaf Extract API.

    Args:
        api_key: Your Kaf Extract API key (starts with 'kaf_').
        base_url: API base URL. Defaults to production.
        timeout: Request timeout in seconds.

    Example:
        client = KafExtract(api_key="kaf_abc123")
        result = client.extract("https://books.toscrape.com", fields=[
            {"name": "title", "selector": "h1", "type": "text"},
        ])
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://extract.kafcenter.com",
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._access_token: str | None = None
        self._client: httpx.AsyncClient | None = None

    def _get_auth_headers(self) -> dict[str, str]:
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_auth_headers(),
            )
        return self._client

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ── Auth ───────────────────────────────────────────────────────

    async def register(
        self, email: str, password: str, name: str | None = None
    ) -> TokenResponse:
        """Register a new user account. Returns JWT tokens."""
        client = await self._get_client()
        resp = await client.post(
            "/auth/register",
            json=RegisterRequest(email=email, password=password, name=name).model_dump(),
        )
        self._raise_for_status(resp)
        return TokenResponse(**resp.json())

    async def login(self, email: str, password: str) -> TokenResponse:
        """Login and get JWT tokens. Sets access token on client."""
        client = await self._get_client()
        resp = await client.post(
            "/auth/login", json=LoginRequest(email=email, password=password).model_dump()
        )
        self._raise_for_status(resp)
        data = TokenResponse(**resp.json())
        self._access_token = data.access_token
        # Update client headers
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {self._access_token}"
        return data

    async def me(self) -> UserResponse:
        """Get the current authenticated user profile."""
        client = await self._get_client()
        resp = await client.get("/auth/me")
        self._raise_for_status(resp)
        return UserResponse(**resp.json())

    async def change_password(self, current_password: str, new_password: str) -> dict:
        """Change the current user's password."""
        client = await self._get_client()
        resp = await client.put(
            "/auth/me/password",
            json={"current_password": current_password, "new_password": new_password},
        )
        self._raise_for_status(resp)
        return resp.json()

    # ── Core Extraction ────────────────────────────────────────────

    async def extract(
        self,
        url: str,
        fields: list[dict[str, Any]],
        base_selector: str | None = None,
        webhook_url: str | None = None,
        async_mode: bool = False,
        output_format: str | None = None,
    ) -> ExtractResponse | str:
        """Extract structured data from a URL.

        Args:
            url: The URL to extract data from.
            fields: List of field definitions. Each field is a dict with:
                - name (str): Field name in output JSON
                - selector (str): CSS/XPath selector
                - type (str): 'text', 'html', 'attribute', 'exists',
                             'markdown', 'screenshot', or 'ai'
                - attribute (str, optional): Attribute name for type='attribute'
                - instruction (str, optional): AI prompt for type='ai'
            base_selector: Optional CSS selector limiting extraction scope.
            webhook_url: Receive results via POST when async job completes.
            async_mode: If True, returns job_id immediately. Poll with get_job().
            output_format: 'csv' or 'markdown' for transformed output.

        Returns:
            ExtractResponse with status, data, and metadata.

        Example:
            result = await client.extract("https://example.com", fields=[
                {"name": "title", "selector": "h1", "type": "text"},
                {"name": "price", "selector": ".price", "type": "text"},
            ])
            print(result.data["title"])
        """
        schema_fields = [FieldSchema(**f) for f in fields]
        schema = ExtractSchema(fields=schema_fields, base_selector=base_selector)

        params = {}
        if async_mode:
            params["async"] = "true"

        client = await self._get_client()
        resp = await client.post(
            "/api/v1/extract",
            json={
                "url": url,
                "schema": schema.model_dump(),
                "webhook_url": webhook_url,
            },
            params=params,
        )
        self._raise_for_status(resp)

        if output_format and not async_mode:
            return resp.text

        return ExtractResponse(**resp.json())

    def extract_sync(
        self,
        url: str,
        fields: list[dict[str, Any]],
        **kwargs,
    ) -> ExtractResponse:
        """Synchronous wrapper for extract()."""
        return asyncio.run(self.extract(url, fields, **kwargs))

    # ── Batch Extraction ───────────────────────────────────────────

    async def extract_batch(
        self,
        urls: list[str],
        fields: list[dict[str, Any]],
        base_selector: str | None = None,
        webhook_url: str | None = None,
        async_mode: bool = False,
    ) -> BatchExtractResponse:
        """Extract data from multiple URLs in parallel (up to 50).

        All URLs share the same extraction schema.
        """
        schema_fields = [FieldSchema(**f) for f in fields]
        schema = ExtractSchema(fields=schema_fields, base_selector=base_selector)

        params = {}
        if async_mode:
            params["async"] = "true"

        client = await self._get_client()
        resp = await client.post(
            "/api/v1/extract/batch",
            json={
                "urls": urls,
                "schema": schema.model_dump(),
                "webhook_url": webhook_url,
            },
            params=params,
        )
        self._raise_for_status(resp)
        return BatchExtractResponse(**resp.json())

    # ── Job Polling ────────────────────────────────────────────────

    async def get_job(self, job_id: str) -> ExtractResponse:
        """Poll for an async extraction job result."""
        client = await self._get_client()
        resp = await client.get(f"/api/v1/extract/{job_id}")
        self._raise_for_status(resp)
        return ExtractResponse(**resp.json())

    # ── AI Extraction ──────────────────────────────────────────────

    async def extract_ai(
        self,
        url: str,
        instruction: str,
        model: str = "kimi-k2.6:cloud",
        output_format: str = "json",
    ) -> ExtractResponse:
        """Extract data using AI (no selectors needed).

        Args:
            url: The URL to extract from.
            instruction: Natural language instruction for what to extract.
                E.g., "Extract the product name, price, and description as JSON."
            model: Ollama model to use. 'kimi-k2.6:cloud' (default) or 'glm-5.1:cloud'.
            output_format: 'json' for structured output or 'text' for raw LLM response.

        Example:
            result = await client.extract_ai(
                "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/",
                instruction="Extract the book title, price, and availability as JSON",
            )
        """
        client = await self._get_client()
        resp = await client.post(
            "/api/v1/extract/ai",
            json=AIExtractRequest(
                url=url, instruction=instruction, model=model, format=output_format
            ).model_dump(),
        )
        self._raise_for_status(resp)
        return ExtractResponse(**resp.json())

    # ── Screenshot ─────────────────────────────────────────────────

    async def screenshot(
        self,
        url: str,
        full_page: bool = False,
        selector: str | None = None,
    ) -> ScreenshotResponse:
        """Capture a screenshot of a URL.

        Args:
            url: The URL to screenshot.
            full_page: Capture the full scrollable page (not just viewport).
            selector: CSS selector to capture only a specific element.

        Returns:
            ScreenshotResponse with base64-encoded PNG in data.screenshot.
        """
        client = await self._get_client()
        resp = await client.post(
            "/api/v1/extract/screenshot",
            json=ScreenshotRequest(
                url=url, full_page=full_page, selector=selector
            ).model_dump(),
        )
        self._raise_for_status(resp)
        return ScreenshotResponse(**resp.json())

    def save_screenshot(self, response: ScreenshotResponse, path: str) -> str:
        """Save a base64 screenshot response to a file.

        Returns:
            The file path.
        """
        if response.data and response.data.screenshot:
            with open(path, "wb") as f:
                f.write(base64.b64decode(response.data.screenshot))
        return path

    # ── Vouchers ───────────────────────────────────────────────────

    async def redeem_voucher(self, code: str) -> dict:
        """Redeem a voucher code for credits/subscription."""
        client = await self._get_client()
        resp = await client.post("/api/v1/vouchers/redeem", json={"code": code})
        self._raise_for_status(resp)
        return resp.json()

    async def voucher_history(self) -> list[dict]:
        """Get the current user's voucher redemption history."""
        client = await self._get_client()
        resp = await client.get("/api/v1/vouchers/history")
        self._raise_for_status(resp)
        return resp.json()

    # ── Health ─────────────────────────────────────────────────────

    async def health(self) -> dict:
        """Check API health (no auth required)."""
        client = await self._get_client()
        resp = await client.get("/health")
        return resp.json()

    # ── Helpers ────────────────────────────────────────────────────

    def _raise_for_status(self, resp: httpx.Response):
        if resp.is_success:
            return
        detail = resp.text
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            pass
        raise KafExtractError(
            f"HTTP {resp.status_code}: {detail}",
            status_code=resp.status_code,
            response=resp.json() if "application/json" in resp.headers.get("content-type", "") else None,
        )
