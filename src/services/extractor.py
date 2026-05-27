"""Playwright-based web data extraction service."""

import asyncio
import time
from typing import Any

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from src.config import settings


class ExtractionError(Exception):
    """Raised when extraction fails for any reason."""


class ExtractorService:
    """Extracts structured data from web pages using Playwright."""

    async def extract(self, url: str, fields: list[dict]) -> dict[str, Any]:
        """
        Extract fields from a web page.

        Args:
            url: The URL to extract data from.
            fields: List of field dicts with keys: name, selector, type, attribute.

        Returns:
            Dict mapping field names to their extracted values.
        """
        results: dict[str, Any] = {}
        start = time.monotonic()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.playwright_headless)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=settings.playwright_timeout_ms)

                for field in fields:
                    try:
                        value = await self._extract_field(page, field)
                        results[field["name"]] = value
                    except Exception as e:
                        results[field["name"]] = None
            except PlaywrightTimeout:
                raise ExtractionError(f"Page load timed out after {settings.playwright_timeout_ms}ms: {url}")
            except Exception as e:
                raise ExtractionError(f"Failed to load page: {url} — {e}")
            finally:
                await browser.close()

        return results

    async def _extract_field(self, page, field: dict) -> Any:
        """Extract a single field from the page."""
        selector = field["selector"]
        field_type = field.get("type", "text")
        attribute = field.get("attribute")

        try:
            element = await page.wait_for_selector(selector, timeout=10000)
            if not element:
                raise ValueError(f"Selector not found: {selector}")
        except PlaywrightTimeout:
            raise ValueError(f"Selector timed out: {selector}")
        except Exception:
            raise ValueError(f"Selector not found: {selector}")

        if field_type == "text":
            return await element.inner_text()
        elif field_type == "html":
            return await element.inner_html()
        elif field_type == "attribute":
            if not attribute:
                raise ValueError("attribute field type requires 'attribute' key")
            return await element.get_attribute(attribute)
        elif field_type == "exists":
            return True
        else:
            return await element.inner_text()


# Singleton
extractor_service = ExtractorService()
