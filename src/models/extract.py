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
