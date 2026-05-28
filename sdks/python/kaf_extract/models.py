"""Type definitions for Kaf Extract API responses."""

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Extraction Schema ──────────────────────────────────────────────

class FieldSchema(BaseModel):
    """A single field to extract from a page."""

    name: str = Field(..., description="Name of the field in the output JSON")
    selector: str = Field(
        default="",
        description="CSS or XPath selector. Required for text/html/attribute/exists types.",
    )
    type: str = Field(
        default="text",
        description="Extraction type: text, html, attribute, exists, markdown, screenshot, ai",
    )
    attribute: Optional[str] = Field(
        default=None, description="Attribute name when type=attribute"
    )
    instruction: Optional[str] = Field(
        default=None,
        description="Natural-language instruction for AI-based extraction (type=ai).",
    )


class ExtractSchema(BaseModel):
    """Schema defining what to extract from a page."""

    fields: list[FieldSchema] = Field(..., min_length=1)
    base_selector: Optional[str] = None


# ── Request Bodies ─────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    """Request body for POST /api/v1/extract."""

    model_config = {"populate_by_name": True}

    url: str
    extraction_schema: ExtractSchema = Field(..., alias="schema")
    webhook_url: Optional[str] = None


class BatchExtractRequest(BaseModel):
    """Request body for POST /api/v1/extract/batch."""

    model_config = {"populate_by_name": True}

    urls: list[str] = Field(..., min_length=1, max_length=50)
    extraction_schema: ExtractSchema = Field(..., alias="schema")
    webhook_url: Optional[str] = None


class AIExtractRequest(BaseModel):
    """Request body for POST /api/v1/extract/ai — natural-language extraction."""

    url: str
    instruction: str = Field(..., min_length=1)
    model: str = Field(default="kimi-k2.6:cloud")
    format: str = Field(default="json")


class ScreenshotRequest(BaseModel):
    """Request body for POST /api/v1/extract/screenshot."""

    url: str
    full_page: bool = False
    selector: Optional[str] = None


# ── Auth ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    role: str
    status: str
    created_at: str


# ── Response Bodies ────────────────────────────────────────────────

class ExtractMetadata(BaseModel):
    url: str
    duration_ms: int
    timestamp: str


class ExtractResponse(BaseModel):
    status: str = "success"
    data: Optional[dict[str, Any]] = None
    metadata: Optional[ExtractMetadata] = None


class BatchResult(BaseModel):
    url: str
    status: str
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class BatchExtractResponse(BaseModel):
    results: list[BatchResult]
    total: int
    succeeded: int
    failed: int


class ScreenshotData(BaseModel):
    screenshot: str = Field(..., description="Base64-encoded PNG screenshot")
    format: str = "png"


class ScreenshotResponse(BaseModel):
    status: str = "success"
    data: Optional[ScreenshotData] = None
    metadata: Optional[ExtractMetadata] = None


class VoucherResponse(BaseModel):
    code: str
    plan: Optional[str] = None
    duration_days: Optional[int] = None
    extraction_credits: Optional[int] = None
    expires_at: Optional[str] = None
    status: str


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    provider: Optional[str] = None
