"""Crawl4AI-based web data extraction service.

Replaces raw Playwright extraction with Crawl4AI's JsonCssExtractionStrategy
for CSS-selector-based extraction and LLMExtractionStrategy for AI-powered
extraction via Ollama.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from crawl4ai import (
    AsyncWebCrawler,
    CacheMode,
    CrawlerRunConfig,
    JsonCssExtractionStrategy,
    LLMConfig,
    LLMExtractionStrategy,
)

from src.config import settings
from src.services.crawl4ai_config import get_browser_config, get_run_config


class ExtractionError(Exception):
    """Raised when extraction fails for any reason."""


class ExtractorService:
    """Extracts structured data from web pages using Crawl4AI.

    Supports:
    - CSS/XPath extraction via JsonCssExtractionStrategy
    - AI/LLM extraction via LLMExtractionStrategy (Ollama)
    - Markdown and screenshot extraction via Crawl4AI core
    """

    def __init__(self) -> None:
        self._crawler: AsyncWebCrawler | None = None

    async def _get_crawler(self) -> AsyncWebCrawler:
        """Get or lazily create the AsyncWebCrawler singleton."""
        if self._crawler is None:
            browser_config = get_browser_config()
            self._crawler = AsyncWebCrawler(config=browser_config)
            await self._crawler.start()
        return self._crawler

    async def extract(self, url: str, fields: list[dict]) -> dict[str, Any]:
        """Extract fields from a web page.

        Args:
            url: The URL to extract data from.
            fields: List of field dicts with keys:
                - name: field name in output
                - selector: CSS/XPath selector
                - type: text, html, attribute, exists, markdown, screenshot, ai
                - attribute: attribute name (for type=attribute)
                - instruction: AI extraction instruction (for type=ai)

        Returns:
            Dict mapping field names to their extracted values.
        """
        if not fields:
            return {}

        start = time.monotonic()

        # Categorize fields
        css_fields: list[dict] = []
        ai_fields: list[dict] = []
        wants_markdown = False
        wants_screenshot = False

        for field in fields:
            ftype = field.get("type", "text")
            if ftype == "ai":
                ai_fields.append(field)
            elif ftype == "markdown":
                wants_markdown = True
            elif ftype == "screenshot":
                wants_screenshot = True
            else:
                # text, html, attribute, exists — all CSS-based
                css_fields.append(field)

        result = await self._do_extract(
            url=url,
            css_fields=css_fields,
            ai_fields=ai_fields,
            screenshot=wants_screenshot,
        )

        # Build output dict
        output: dict[str, Any] = {}

        # Parse CSS extraction results (from JsonCssExtractionStrategy)
        if css_fields and result.css_data is not None:
            output.update(self._parse_css_results(css_fields, result.css_data))

        # Parse AI extraction results (from LLMExtractionStrategy)
        if ai_fields and result.ai_data is not None:
            output.update(self._parse_ai_results(ai_fields, result.ai_data))

        # Add markdown if requested
        if wants_markdown:
            for f in fields:
                if f.get("type") == "markdown":
                    output[f["name"]] = result.markdown

        # Add screenshot if requested
        if wants_screenshot:
            for f in fields:
                if f.get("type") == "screenshot":
                    output[f["name"]] = result.screenshot

        return output

    async def _do_extract(
        self,
        url: str,
        css_fields: list[dict],
        ai_fields: list[dict],
        screenshot: bool,
    ) -> _ExtractResult:
        """Run the Crawl4AI crawl with appropriate extraction strategy.

        If there are AI fields, runs a single crawl with LLMExtractionStrategy.
        Otherwise, runs a crawl with JsonCssExtractionStrategy for CSS fields.
        """
        crawler = await self._get_crawler()

        # Determine extraction strategy
        extraction_strategy = None

        if ai_fields:
            extraction_strategy = self._build_ai_strategy(ai_fields)
        elif css_fields:
            extraction_strategy = self._build_css_strategy(css_fields)

        run_config = get_run_config(
            extraction_strategy=extraction_strategy,
            screenshot=screenshot,
            cache_mode=CacheMode.ENABLED,
        )

        try:
            crawl_result = await crawler.arun(url=url, config=run_config)
        except Exception as e:
            raise ExtractionError(f"Crawl4AI extraction failed for {url}: {e}")

        if not crawl_result.success:
            error_msg = crawl_result.error_message or "Unknown error"
            raise ExtractionError(f"Page load failed for {url}: {error_msg}")

        # Parse extracted_content
        css_data = None
        ai_data = None

        if crawl_result.extracted_content:
            try:
                parsed = json.loads(crawl_result.extracted_content)
                if ai_fields:
                    ai_data = parsed
                else:
                    css_data = parsed
            except (json.JSONDecodeError, TypeError):
                pass

        return _ExtractResult(
            css_data=css_data,
            ai_data=ai_data,
            markdown=crawl_result.markdown or "",
            screenshot=crawl_result.screenshot or "",
        )

    def _build_css_strategy(self, fields: list[dict]) -> JsonCssExtractionStrategy:
        """Build a JsonCssExtractionStrategy from CSS field definitions.

        Maps the flat field list to Crawl4AI's schema format:
        {"name": "Extraction", "baseSelector": "html", "fields": [...]}
        """
        schema_fields: list[dict] = []
        for field in fields:
            ftype = field.get("type", "text")
            entry: dict = {
                "name": field["name"],
                "selector": field.get("selector", ""),
                "type": ftype,
            }
            if ftype == "attribute":
                entry["attribute"] = field.get("attribute", "")
            elif ftype == "exists":
                # JsonCssExtractionStrategy doesn't have an "exists" type directly.
                # We use "text" with a default of "true" / False and check for content.
                entry["type"] = "text"
                entry["default"] = None  # Will be None if not found
            schema_fields.append(entry)

        schema = {
            "name": "Extraction",
            "baseSelector": "body",
            "fields": schema_fields,
        }

        return JsonCssExtractionStrategy(schema=schema, verbose=settings.crawl4ai_verbose)

    def _build_ai_strategy(self, fields: list[dict]) -> LLMExtractionStrategy:
        """Build an LLMExtractionStrategy for AI-powered extraction via Ollama.

        Uses the instruction from each field to describe what to extract.
        """
        # Build a combined instruction
        field_descriptions = []
        for field in fields:
            instr = field.get("instruction", f"Extract the value of '{field['name']}'")
            field_descriptions.append(f"- {field['name']}: {instr}")
        instruction = (
            "Extract the following fields from the page content. "
            "Return a JSON object with these exact field names as keys:\n"
            + "\n".join(field_descriptions)
        )

        # Build schema for structured extraction
        field_names = [f["name"] for f in fields]
        extraction_schema = {
            "type": "object",
            "properties": {name: {"type": "string"} for name in field_names},
            "required": field_names,
        }

        llm_config = LLMConfig(
            provider=f"ollama/{settings.ollama_model}",
            api_token=settings.ollama_api_key,
            base_url=settings.ollama_base_url,
        )

        return LLMExtractionStrategy(
            llm_config=llm_config,
            instruction=instruction,
            schema=extraction_schema,
            extraction_type="schema",
            force_json_response=True,
            verbose=settings.crawl4ai_verbose,
            provider=f"ollama/{settings.ollama_model}",
            api_token=settings.ollama_api_key,
            base_url=settings.ollama_base_url,
        )

    def _parse_css_results(
        self, fields: list[dict], css_data: Any
    ) -> dict[str, Any]:
        """Parse results from JsonCssExtractionStrategy.

        The strategy returns a list of items. Since we use "body" as baseSelector,
        we get a single-item list. Extract field values, handling 'exists' specially.
        """
        output: dict[str, Any] = {}

        if isinstance(css_data, list) and css_data:
            item = css_data[0]
        elif isinstance(css_data, dict):
            item = css_data
        else:
            return output

        for field in fields:
            name = field["name"]
            ftype = field.get("type", "text")

            if ftype == "exists":
                # For 'exists', check if the field was extracted (non-None)
                raw_value = item.get(name)
                # JsonCssExtractionStrategy returns empty string for missing text fields
                # and None only if default=None was set. We'll treat non-empty truthy as True.
                output[name] = bool(raw_value) if raw_value else False
            else:
                output[name] = item.get(name)

        return output

    def _parse_ai_results(
        self, fields: list[dict], ai_data: Any
    ) -> dict[str, Any]:
        """Parse results from LLMExtractionStrategy.

        The strategy returns a JSON object with field names as keys.
        """
        output: dict[str, Any] = {}

        if isinstance(ai_data, dict):
            for field in fields:
                name = field["name"]
                output[name] = ai_data.get(name)
        elif isinstance(ai_data, list) and ai_data:
            # Some LLM responses come as a list
            item = ai_data[0] if isinstance(ai_data[0], dict) else {}
            for field in fields:
                name = field["name"]
                output[name] = item.get(name)

        return output

    async def close(self) -> None:
        """Close the crawler and release resources."""
        if self._crawler:
            await self._crawler.close()
            self._crawler = None


class _ExtractResult:
    """Internal result holder for extraction data."""

    __slots__ = ("css_data", "ai_data", "markdown", "screenshot")

    def __init__(
        self,
        css_data: Any = None,
        ai_data: Any = None,
        markdown: str = "",
        screenshot: str = "",
    ) -> None:
        self.css_data = css_data
        self.ai_data = ai_data
        self.markdown = markdown
        self.screenshot = screenshot


# Singleton
extractor_service = ExtractorService()
