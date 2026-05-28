"""Pydantic models for the extraction API."""

from typing import Any

from pydantic import BaseModel, Field


class FieldSchema(BaseModel):
    """A single field to extract from a page."""

    name: str = Field(..., description="Name of the field in the output JSON")
    selector: str = Field(
        default="",
        description="CSS or XPath selector. Required for text/html/attribute/exists types. "
                    "Ignored for markdown, screenshot, and ai types.",
    )
    type: str = Field(
        default="text",
        description="Extraction type: text, html, attribute, exists, markdown, screenshot, ai",
    )
    attribute: str | None = Field(
        default=None, description="Attribute name when type=attribute"
    )
    instruction: str | None = Field(
        default=None,
        description="Natural-language instruction for AI-based extraction (type=ai). "
                    "E.g., 'Extract the main article title' or 'Get the product price as a number'.",
    )


class ExtractSchema(BaseModel):
    """Schema defining what to extract from a page."""

    fields: list[FieldSchema] = Field(..., min_length=1, description="Fields to extract")
    base_selector: str | None = Field(
        default=None,
        description="Optional CSS selector for a common container element. "
                    "When set, all field selectors are relative to this element.",
    )


class ExtractRequest(BaseModel):
    """Request body for POST /api/v1/extract."""

    url: str = Field(..., description="URL to extract data from")
    schema: ExtractSchema = Field(..., description="Extraction schema")
    webhook_url: str | None = Field(
        default=None,
        description="Optional webhook URL to POST results to when async extraction completes. "
                    "Receives a JSON payload with the extraction result, signed with HMAC-SHA256 "
                    "via X-Kaf-Signature header.",
    )


class BatchExtractRequest(BaseModel):
    """Request body for POST /api/v1/extract/batch."""

    urls: list[str] = Field(..., min_length=1, max_length=50, description="URLs to extract data from")
    schema: ExtractSchema = Field(..., description="Extraction schema applied to each URL")
    webhook_url: str | None = Field(
        default=None,
        description="Optional webhook URL to POST results to when batch extraction completes.",
    )


class BatchResult(BaseModel):
    """Result for a single URL in a batch extraction."""

    url: str
    status: str  # "success" or "error"
    data: dict[str, Any] | None = None
    error: str | None = None


class BatchExtractResponse(BaseModel):
    """Response body for POST /api/v1/extract/batch."""

    results: list[BatchResult]
    total: int
    succeeded: int
    failed: int


class FieldResult(BaseModel):
    """Result for a single extracted field."""

    name: str
    value: Any = None
    error: str | None = None


class ExtractMetadata(BaseModel):
    """Metadata about the extraction operation."""

    url: str
    duration_ms: int
    timestamp: str


class ExtractResponse(BaseModel):
    """Response body for POST /api/v1/extract."""

    status: str = "success"
    data: dict[str, Any] | None = None
    metadata: ExtractMetadata | None = None


class ErrorResponse(BaseModel):
    """Response body for errors."""

    status: str = "error"
    error: dict[str, str]


# ---------------------------------------------------------------------------
# P2-3: LLM extraction endpoint
# ---------------------------------------------------------------------------


class AIExtractRequest(BaseModel):
    """Request body for POST /api/v1/extract/ai — natural-language extraction."""

    url: str = Field(..., description="URL to extract data from")
    instruction: str = Field(
        ..., min_length=1,
        description="Natural-language description of what to extract. "
                    "E.g., 'Extract the main article title and author name as JSON'.",
    )
    model: str = Field(
        default="kimi-k2.6:cloud",
        description="Ollama model to use: 'kimi-k2.6:cloud' or 'glm-5.1:cloud'",
    )
    format: str = Field(
        default="json",
        description="Output format: 'json' (structured) or 'text' (raw LLM response)",
    )


class AIExtractResponse(BaseModel):
    """Response body for POST /api/v1/extract/ai."""

    status: str = "success"
    data: dict[str, Any] | str | None = None
    metadata: ExtractMetadata | None = None


# ---------------------------------------------------------------------------
# P2-4: Screenshot endpoint
# ---------------------------------------------------------------------------


class ScreenshotRequest(BaseModel):
    """Request body for POST /api/v1/extract/screenshot."""

    url: str = Field(..., description="URL to capture screenshot of")
    full_page: bool = Field(
        default=False,
        description="Capture the full scrollable page instead of just the viewport",
    )
    selector: str | None = Field(
        default=None,
        description="Optional CSS selector to screenshot a specific element only",
    )


class ScreenshotData(BaseModel):
    """Screenshot data returned in the response."""

    screenshot: str = Field(..., description="Base64-encoded PNG screenshot")
    format: str = Field(default="png", description="Image format")


class ScreenshotResponse(BaseModel):
    """Response body for POST /api/v1/extract/screenshot."""

    status: str = "success"
    data: ScreenshotData | None = None
    metadata: ExtractMetadata | None = None
