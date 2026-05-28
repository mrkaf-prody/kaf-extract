"""Crawl4AI configuration — BrowserConfig and CrawlerRunConfig defaults."""

from crawl4ai import BrowserConfig, CacheMode, CrawlerRunConfig

from src.config import settings


def get_browser_config() -> BrowserConfig:
    """Build a BrowserConfig for Crawl4AI with sensible defaults.

    Includes Docker-friendly args (--no-sandbox, etc.) and respects
    CRAWL4AI_CHROME_PATH for custom Chrome installations.
    """
    extra_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
    ]

    config_kwargs: dict = {
        "headless": settings.crawl4ai_headless,
        "browser_type": "chromium",
        "verbose": settings.crawl4ai_verbose,
        "extra_args": extra_args,
    }

    # Custom Chrome path for local dev or non-standard installations
    if settings.crawl4ai_chrome_path:
        config_kwargs["chrome_channel"] = "chromium"
        # Crawl4AI uses executable_path via BrowserConfig, but the field name
        # may vary by version. We inject it as a kwarg that Playwright will pick up.
        config_kwargs["executable_path"] = settings.crawl4ai_chrome_path

    return BrowserConfig(**config_kwargs)


def get_run_config(
    extraction_strategy=None,
    css_selector: str | None = None,
    screenshot: bool = False,
    cache_mode: CacheMode = CacheMode.ENABLED,
) -> CrawlerRunConfig:
    """Build a CrawlerRunConfig with caching enabled and extraction strategy.

    Args:
        extraction_strategy: JsonCssExtractionStrategy, LLMExtractionStrategy, etc.
        css_selector: Optional CSS selector to scope extraction.
        screenshot: Whether to capture a screenshot.
        cache_mode: Caching mode (default: ENABLED).

    Returns:
        Configured CrawlerRunConfig instance.
    """
    return CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        css_selector=css_selector,
        screenshot=screenshot,
        cache_mode=cache_mode,
        page_timeout=settings.crawl4ai_page_timeout_ms,
        verbose=settings.crawl4ai_verbose,
        wait_until="domcontentloaded",
    )
