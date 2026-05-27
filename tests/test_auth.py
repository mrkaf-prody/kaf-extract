"""Tests for auth and API key validation."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_extract_missing_api_key(client):
    response = await client.post("/api/v1/extract", json={
        "url": "https://example.com",
        "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]}
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_extract_invalid_api_key(client):
    response = await client.post(
        "/api/v1/extract",
        json={
            "url": "https://example.com",
            "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]}
        },
        headers={"X-API-Key": "invalid-key"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_extract_invalid_url(client):
    response = await client.post(
        "/api/v1/extract",
        json={
            "url": "not-a-valid-url",
            "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]}
        },
        headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"}
    )
    assert response.status_code in (422, 500)


@pytest.mark.asyncio
async def test_extract_empty_fields(client):
    response = await client.post(
        "/api/v1/extract",
        json={
            "url": "https://example.com",
            "schema": {"fields": []}
        },
        headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"}
    )
    assert response.status_code == 422
