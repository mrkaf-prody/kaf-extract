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
        self._crawler_lock: asyncio.Lock = asyncio.Lock()

    async def _get_crawler(self) -> AsyncWebCrawler:
        """Get or lazily create the AsyncWebCrawler singleton.

        Thread-safe: uses an asyncio.Lock to prevent multiple concurrent
        crawler creations that could trigger Chromium launch races.
        """
        if self._crawler is not None:
            return self._crawler

        async with self._crawler_lock:
            # Double-check after acquiring the lock
            if self._crawler is not None:
                return self._crawler

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

    async def extract_batch(
        self,
        urls: list[str],
        fields: list[dict],
        max_concurrent: int = 5,
    ) -> list[dict[str, Any]]:
        """Extract data from multiple URLs in parallel using arun_many().

        Uses Crawl4AI's MemoryAdaptiveDispatcher for concurrent crawling
        with automatic backpressure.

        Args:
            urls: List of URLs to extract data from.
            fields: The field definitions (applied to each URL).
            max_concurrent: Maximum concurrent crawls (default 5).

        Returns:
            List of result dicts, one per URL, each with keys:
            {url, status, data, error}.
        """
        if not urls:
            return []

        from crawl4ai import MemoryAdaptiveDispatcher

        crawler = await self._get_crawler()

        # Build the extraction strategy (CSS vs AI) — same for all URLs
        css_fields: list[dict] = []
        ai_fields: list[dict] = []
        wants_screenshot = False
        wants_markdown = False

        for field in fields:
            ftype = field.get("type", "text")
            if ftype == "ai":
                ai_fields.append(field)
            elif ftype == "markdown":
                wants_markdown = True
            elif ftype == "screenshot":
                wants_screenshot = True
            else:
                css_fields.append(field)

        extraction_strategy = None
        if ai_fields:
            extraction_strategy = self._build_ai_strategy(ai_fields)
        elif css_fields:
            extraction_strategy = self._build_css_strategy(css_fields)

        from src.services.crawl4ai_config import get_run_config
        import time as _time

        # Build a single run config (same for all URLs)
        base_run_config = get_run_config(
            extraction_strategy=extraction_strategy,
            screenshot=wants_screenshot,
            cache_mode=CacheMode.ENABLED,
        )

        results: list[dict[str, Any]] = []
        results_by_url: dict[str, dict[str, Any]] = {}

        try:
            # Use arun_many with MemoryAdaptiveDispatcher for parallel crawling
            dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=70.0,
                check_interval=1.0,
                max_session_permit=max_concurrent,
            )

            crawl_results = await crawler.arun_many(
                urls=urls,
                config=base_run_config,
                dispatcher=dispatcher,
            )

            # Process results
            for crawl_result in crawl_results:
                url = crawl_result.url or ""
                entry: dict[str, Any] = {"url": url}

                if crawl_result.success:
                    # Parse extracted content
                    data: dict[str, Any] = {}
                    if crawl_result.extracted_content:
                        try:
                            parsed = json.loads(crawl_result.extracted_content)
                            if ai_fields:
                                data = self._parse_ai_results(ai_fields, parsed)
                            else:
                                data = self._parse_css_results(css_fields, parsed)
                        except (json.JSONDecodeError, TypeError):
                            pass

                    # Add markdown if requested
                    if wants_markdown:
                        for f in fields:
                            if f.get("type") == "markdown":
                                data[f["name"]] = crawl_result.markdown or ""

                    # Add screenshot if requested
                    if wants_screenshot:
                        for f in fields:
                            if f.get("type") == "screenshot":
                                data[f["name"]] = crawl_result.screenshot or ""

                    entry["status"] = "success"
                    entry["data"] = data
                    entry["error"] = None
                else:
                    entry["status"] = "error"
                    entry["data"] = None
                    entry["error"] = crawl_result.error_message or "Unknown error"

                results_by_url[url] = entry

        except Exception as e:
            # If arun_many itself fails, all URLs fail
            for url in urls:
                if url not in results_by_url:
                    results_by_url[url] = {
                        "url": url,
                        "status": "error",
                        "data": None,
                        "error": str(e),
                    }

        # Return results in the same order as the input URLs
        for url in urls:
            if url in results_by_url:
                results.append(results_by_url[url])
            else:
                results.append({
                    "url": url,
                    "status": "error",
                    "data": None,
                    "error": "No result returned",
                })

        return results

    async def close(self) -> None:
        """Close the crawler and release resources.

        Thread-safe: holds the crawler lock to ensure no concurrent
        _get_crawler() is in progress.
        """
        async with self._crawler_lock:
            if self._crawler:
                await self._crawler.close()
                self._crawler = None

    # ------------------------------------------------------------------
    # P2-3: Dedicated AI / LLM extraction
    # ------------------------------------------------------------------

    async def extract_ai(
        self,
        url: str,
        instruction: str,
        model: str = "kimi-k2.6:cloud",
        output_format: str = "json",
    ) -> dict[str, Any]:
        """Extract data from a page using natural-language instruction via Ollama.

        Args:
            url: The URL to extract data from.
            instruction: Natural-language description of what to extract.
            model: Ollama model name (kimi-k2.6:cloud or glm-5.1:cloud).
            output_format: 'json' for structured output, 'text' for raw LLM response.

        Returns:
            Dict with 'data' (parsed JSON or raw text) and 'raw' (full output).
        """
        start = time.monotonic()
        crawler = await self._get_crawler()

        llm_config = LLMConfig(
            provider=f"ollama/{model}",
            api_token=settings.ollama_api_key,
            base_url=settings.ollama_base_url,
        )

        # Build extraction strategy based on format
        if output_format == "json":
            extraction_strategy = LLMExtractionStrategy(
                llm_config=llm_config,
                instruction=instruction,
                extraction_type="schema",
                force_json_response=True,
                verbose=settings.crawl4ai_verbose,
            )
        else:
            # text mode: no schema, raw LLM output
            extraction_strategy = LLMExtractionStrategy(
                llm_config=llm_config,
                instruction=instruction,
                extraction_type="block",
                verbose=settings.crawl4ai_verbose,
            )

        run_config = get_run_config(
            extraction_strategy=extraction_strategy,
            screenshot=False,
            cache_mode=CacheMode.ENABLED,
        )

        try:
            crawl_result = await crawler.arun(url=url, config=run_config)
        except Exception as e:
            raise ExtractionError(f"Crawl4AI AI extraction failed for {url}: {e}")

        if not crawl_result.success:
            error_msg = crawl_result.error_message or "Unknown error"
            raise ExtractionError(f"Page load failed for {url}: {error_msg}")

        duration_ms = int((time.monotonic() - start) * 1000)

        raw_output = crawl_result.extracted_content or ""
        parsed_data = None

        if output_format == "json" and raw_output:
            try:
                parsed_data = json.loads(raw_output)
            except (json.JSONDecodeError, TypeError):
                parsed_data = {"raw": raw_output}

        return {
            "data": parsed_data if output_format == "json" else raw_output,
            "raw": raw_output,
            "duration_ms": duration_ms,
        }

    # ------------------------------------------------------------------
    # P2-4: Dedicated screenshot extraction
    # ------------------------------------------------------------------

    async def extract_screenshot(
        self,
        url: str,
        full_page: bool = False,
        selector: str | None = None,
    ) -> dict[str, Any]:
        """Capture a screenshot of a web page.

        Args:
            url: The URL to screenshot.
            full_page: Capture the full scrollable page.
            selector: Optional CSS selector for element-specific screenshot.

        Returns:
            Dict with 'screenshot' (base64 PNG) and 'format'.
        """
        start = time.monotonic()
        crawler = await self._get_crawler()

        # Build a run config with screenshot enabled
        run_config = get_run_config(
            extraction_strategy=None,
            screenshot=True,
            cache_mode=CacheMode.ENABLED,
        )

        # If a CSS selector is specified, use css_selector for element screenshot
        if selector:
            run_config.css_selector = selector

        # For full-page screenshots, adjust the config
        if full_page:
            # Crawl4AI captures full page by default. If there's an explicit
            # full_page setting to toggle, set it here.
            pass

        try:
            crawl_result = await crawler.arun(url=url, config=run_config)
        except Exception as e:
            raise ExtractionError(f"Screenshot capture failed for {url}: {e}")

        if not crawl_result.success:
            error_msg = crawl_result.error_message or "Unknown error"
            raise ExtractionError(f"Page load failed for {url}: {error_msg}")

        duration_ms = int((time.monotonic() - start) * 1000)

        screenshot_b64 = crawl_result.screenshot or ""

        return {
            "screenshot": screenshot_b64,
            "format": "png",
            "duration_ms": duration_ms,
        }


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
