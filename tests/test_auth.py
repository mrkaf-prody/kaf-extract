"""Tests for JWT auth — register, login, refresh, me."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Unit tests for auth functions (no DB needed)
# ---------------------------------------------------------------------------

class TestTokenCreation:
    """Tests for JWT token creation and decoding."""

    def test_create_and_decode_access_token(self):
        from src.middleware.auth import create_access_token, decode_token

        token = create_access_token(
            user_id="550e8400-e29b-41d4-a716-446655440000",
            email="test@example.com",
            role="user",
        )
        assert isinstance(token, str)
        payload = decode_token(token)
        assert payload["sub"] == "550e8400-e29b-41d4-a716-446655440000"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "user"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_and_decode_refresh_token(self):
        from src.middleware.auth import create_refresh_token, decode_token

        token = create_refresh_token("550e8400-e29b-41d4-a716-446655440000")
        payload = decode_token(token)
        assert payload["sub"] == "550e8400-e29b-41d4-a716-446655440000"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token_raises(self):
        from src.middleware.auth import decode_token
        from jose import JWTError

        with pytest.raises(JWTError):
            decode_token("not-a-valid-token")


class TestPasswordHashing:
    """Tests for password hashing via passlib."""

    def test_hash_and_verify(self):
        from passlib.context import CryptContext
        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed = pwd.hash("test-password")
        assert pwd.verify("test-password", hashed)
        assert not pwd.verify("wrong-password", hashed)


# ---------------------------------------------------------------------------
# Integration tests (httpx against the app, mocking DB)
# ---------------------------------------------------------------------------

class TestAuthEndpoints:
    """Tests for auth router endpoints with mocked DB."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock async DB session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.flush = AsyncMock()
        session.add = AsyncMock()
        session.delete = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_register_new_user(self, client, mock_db_session):
        """POST /auth/register with a new email should return tokens."""
        # Override the get_db dependency at the app level
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        # We need to properly mock the coroutine chain. The route does:
        #   result = await db.execute(select(User).where(...))
        #   if result.scalar_one_or_none():  # <-- this is called sync, returns coroutine
        #       raise HTTPException(409)
        # We need scalar_one_or_none to return a coroutine that when awaited yields None
        mock_scalar = AsyncMock()
        mock_scalar.return_value = None  # Return None when awaited
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_scalar()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        try:
            response = await client.post("/auth/register", json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "name": "Test User",
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_short_password(self, client):
        """POST /auth/register with password < 8 chars should fail validation."""
        response = await client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "short",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client):
        """POST /auth/register with invalid email should fail validation."""
        response = await client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "securepassword123",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client):
        """POST /auth/login without required fields should fail."""
        response = await client.post("/auth/login", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client, mock_db_session):
        """POST /auth/refresh with an invalid token should fail."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        mock_result = AsyncMock()
        mock_result.scalars.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        try:
            response = await client.post("/auth/refresh", json={
                "refresh_token": "not-a-valid-token-at-all",
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_without_token(self, client):
        """GET /auth/me without Authorization header should fail."""
        response = await client.get("/auth/me")
        assert response.status_code in (401, 403)  # HTTPBearer returns 401 or 403 depending on version


# ---------------------------------------------------------------------------
# Backward compat — API key tests
# ---------------------------------------------------------------------------

class TestApiKeyAuth:
    """Tests for API key authentication (backward compat)."""

    @pytest.mark.asyncio
    async def test_extract_missing_api_key(self, client):
        response = await client.post("/api/v1/extract", json={
            "url": "https://example.com",
            "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]}
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_extract_invalid_api_key(self, client):
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
    async def test_extract_dev_key(self, client):
        """Test that the dev API key passes auth (may fail on extraction or env)."""
        response = await client.post(
            "/api/v1/extract",
            json={
                "url": "https://example.com",
                "schema": {"fields": [{"name": "test", "selector": "body", "type": "text"}]}
            },
            headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"}
        )
        # Auth should pass (dev key). Extraction may fail due to env (no Playwright, etc.)
        # Accept 200, 422 (extraction error), or 500 (Playwright not installed)
        assert response.status_code in (200, 422, 500)

    @pytest.mark.asyncio
    async def test_extract_empty_fields(self, client):
        response = await client.post(
            "/api/v1/extract",
            json={
                "url": "https://example.com",
                "schema": {"fields": []}
            },
            headers={"X-API-Key": "kaf-extract-dev-key-change-in-production"}
        )
        assert response.status_code == 422
