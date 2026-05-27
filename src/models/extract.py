"""Pydantic models for the extraction API."""

from typing import Any

from pydantic import BaseModel, Field


class FieldSchema(BaseModel):
    """A single field to extract from a page."""

    name: str = Field(..., description="Name of the field in the output JSON")
    selector: str = Field(..., description="CSS or XPath selector")
    type: str = Field(default="text", description="Extraction type: text, html, attribute, exists")
    attribute: str | None = Field(default=None, description="Attribute name when type=attribute")


class ExtractSchema(BaseModel):
    """Schema defining what to extract from a page."""

    fields: list[FieldSchema] = Field(..., min_length=1, description="Fields to extract")


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
