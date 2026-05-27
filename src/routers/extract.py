"""POST /api/v1/extract — Data extraction endpoint."""

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from src.models.apikey import verify_api_key
from src.models.extract import ExtractMetadata, ExtractRequest, ExtractResponse
from src.services.extractor import ExtractionError, extractor_service

router = APIRouter(tags=["extract"])


def validate_api_key(request: Request) -> dict:
    """Dependency: validate X-API-Key header."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    key_info = verify_api_key(api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return key_info


@router.post("/extract", response_model=ExtractResponse)
async def extract_data(
    request: Request,
    body: ExtractRequest,
    key_info: dict = Depends(validate_api_key),
):
    """Extract structured data from a URL using CSS/XPath selectors."""
    start = time.monotonic()

    fields = [
        {
            "name": f.name,
            "selector": f.selector,
            "type": f.type,
            "attribute": f.attribute,
        }
        for f in body.schema.fields
    ]

    try:
        data = await extractor_service.extract(body.url, fields)
    except ExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    duration_ms = int((time.monotonic() - start) * 1000)

    return ExtractResponse(
        status="success",
        data=data,
        metadata=ExtractMetadata(
            url=body.url,
            duration_ms=duration_ms,
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )
