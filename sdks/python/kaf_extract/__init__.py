"""Kaf Extract — AI-powered web data extraction.

Official Python SDK for the Kaf Extract API.
Built on Crawl4AI with Redis caching, async job queue, and AI extraction via Ollama.

Usage:
    from kaf_extract import KafExtract

    client = KafExtract(api_key="kaf_xxxx")
    result = client.extract_sync("https://example.com", fields=[
        {"name": "title", "selector": "h1", "type": "text"},
    ])
"""

from .client import KafExtract, KafExtractError
from .models import (
    AIExtractRequest,
    BatchExtractRequest,
    BatchExtractResponse,
    BatchResult,
    ExtractRequest,
    ExtractResponse,
    ExtractSchema,
    FieldSchema,
    ScreenshotRequest,
    ScreenshotResponse,
    TokenResponse,
    UserResponse,
)

__all__ = [
    "KafExtract",
    "KafExtractError",
    "ExtractRequest",
    "ExtractResponse",
    "ExtractSchema",
    "FieldSchema",
    "BatchExtractRequest",
    "BatchExtractResponse",
    "BatchResult",
    "AIExtractRequest",
    "ScreenshotRequest",
    "ScreenshotResponse",
    "TokenResponse",
    "UserResponse",
]
__version__ = "1.0.0"
