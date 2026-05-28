"""Tests for enhanced health endpoint with DB/Redis status."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_health_db_healthy(client):
    """Health check returns healthy when DB is up."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    with patch(
        "src.routers.health.async_session_factory",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)),
    ):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.2.0"
        assert data["db_status"] == "healthy"
        assert "redis_status" in data


@pytest.mark.asyncio
async def test_health_db_unhealthy(client):
    """Health check returns 503 when DB is down."""
    with patch(
        "src.routers.health.async_session_factory",
        side_effect=Exception("Database connection refused"),
    ):
        response = await client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["status"] == "degraded"
        assert data["detail"]["db_status"] == "unhealthy"


@pytest.mark.asyncio
async def test_health_redis_status_present(client):
    """Health check includes redis_status field."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    with patch(
        "src.routers.health.async_session_factory",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)),
    ), patch(
        "src.routers.health._check_redis",
        new_callable=AsyncMock,
        return_value="unavailable",
    ):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "redis_status" in data
        assert data["redis_status"] in ("healthy", "unavailable")


@pytest.mark.asyncio
async def test_health_fields_present(client):
    """Health check returns all expected fields."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    with patch(
        "src.routers.health.async_session_factory",
        side_effect=None,
    ):
        # Simulate both DB and Redis failing
        with patch(
            "src.routers.health._check_db",
            new_callable=AsyncMock,
            return_value="unhealthy",
        ), patch(
            "src.routers.health._check_redis",
            new_callable=AsyncMock,
            return_value="unavailable",
        ):
            response = await client.get("/health")
            assert response.status_code == 503
            data = response.json()["detail"]
            assert data["status"] == "degraded"
            assert data["version"] == "0.2.0"
            assert data["db_status"] == "unhealthy"
            assert data["redis_status"] == "unavailable"
