"""Tests for API key management endpoints — admin CRUD + user listing."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db
from src.middleware.auth import get_current_user, admin_required


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def mock_db():
    """Create a mock async DB session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    session.execute = AsyncMock()
    return session


def _make_admin_user():
    """Return a mock admin user dict for dependency override."""
    return {
        "user_id": uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),
        "email": "admin@example.com",
        "role": "admin",
    }


def _make_regular_user():
    """Return a mock regular user dict for dependency override."""
    return {
        "user_id": uuid.UUID("550e8400-e29b-41d4-a716-446655440002"),
        "email": "user@example.com",
        "role": "user",
    }


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

class TestAdminCreateKey:
    """POST /api/v1/admin/keys"""

    @pytest.mark.asyncio
    async def test_create_key_success(self, client, mock_db):
        """Admin can create a new API key."""
        # Override dependencies
        async def override_admin():
            return _make_admin_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[admin_required] = override_admin
        app.dependency_overrides[get_db] = override_db

        # Mock User lookup
        from src.models.sql_models import User as UserModel

        mock_user = MagicMock(spec=UserModel)
        mock_user.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440001")
        mock_user.email = "admin@example.com"
        mock_user.status = "active"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        try:
            response = await client.post(
                "/api/v1/admin/keys",
                json={
                    "label": "my-test-key",
                    "tier": "pro",
                    "rate_limit": 200,
                },
            )
        finally:
            app.dependency_overrides.pop(admin_required, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 201
        data = response.json()
        assert data["label"] == "my-test-key"
        assert data["tier"] == "pro"
        assert data["rate_limit"] == 200
        assert "api_key" in data
        assert data["api_key"].startswith("kaf_")
        assert "Store this key securely" in data["message"]

    @pytest.mark.asyncio
    async def test_create_key_requires_admin(self, client, mock_db):
        """Non-admin should get 403 when creating keys."""
        async def override_user():
            return _make_regular_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        try:
            response = await client.post(
                "/api/v1/admin/keys",
                json={
                    "label": "my-key",
                    "tier": "hobby",
                    "rate_limit": 100,
                },
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

        # FastAPI dependency resolution: admin_required calls get_current_user
        # which we overrode; admin_required itself is NOT overridden
        # get_current_user returns a regular user, admin_required checks role
        # Since admin_required is not overridden, it uses the real get_current_user
        # which returns from our override. The real admin_required sees role="user"
        # and raises 403.
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_create_key_invalid_tier(self, client, mock_db):
        """Invalid tier should fail validation."""
        async def override_admin():
            return _make_admin_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[admin_required] = override_admin
        app.dependency_overrides[get_db] = override_db

        try:
            response = await client.post(
                "/api/v1/admin/keys",
                json={
                    "label": "bad-key",
                    "tier": "invalid_tier",
                    "rate_limit": 100,
                },
            )
        finally:
            app.dependency_overrides.pop(admin_required, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_key_empty_label(self, client):
        """Empty label should fail validation."""
        async def override_admin():
            return _make_admin_user()

        app.dependency_overrides[admin_required] = override_admin

        try:
            response = await client.post(
                "/api/v1/admin/keys",
                json={
                    "label": "",
                    "tier": "hobby",
                    "rate_limit": 100,
                },
            )
        finally:
            app.dependency_overrides.pop(admin_required, None)

        assert response.status_code == 422


class TestAdminListKeys:
    """GET /api/v1/admin/keys"""

    @pytest.mark.asyncio
    async def test_list_keys_empty(self, client, mock_db):
        """Admin lists keys, empty result."""
        async def override_admin():
            return _make_admin_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[admin_required] = override_admin
        app.dependency_overrides[get_db] = override_db

        # Mock: no keys
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_result.scalar.return_value = 0  # Total count
        mock_db.execute = AsyncMock(return_value=mock_result)

        try:
            response = await client.get("/api/v1/admin/keys")
        finally:
            app.dependency_overrides.pop(admin_required, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert data["keys"] == []
        assert data["total"] == 0
        assert data["offset"] == 0
        assert data["limit"] == 50

    @pytest.mark.asyncio
    async def test_list_keys_pagination(self, client, mock_db):
        """Admin lists keys with custom offset/limit."""
        async def override_admin():
            return _make_admin_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[admin_required] = override_admin
        app.dependency_overrides[get_db] = override_db

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_result.scalar.return_value = 42
        mock_db.execute = AsyncMock(return_value=mock_result)

        try:
            response = await client.get("/api/v1/admin/keys?offset=10&limit=5")
        finally:
            app.dependency_overrides.pop(admin_required, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 10
        assert data["limit"] == 5

    @pytest.mark.asyncio
    async def test_list_keys_filter_by_invalid_status(self, client, mock_db):
        """Invalid status filter should return 400."""
        async def override_admin():
            return _make_admin_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[admin_required] = override_admin
        app.dependency_overrides[get_db] = override_db

        try:
            response = await client.get("/api/v1/admin/keys?status=deleted")
        finally:
            app.dependency_overrides.pop(admin_required, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 400


class TestAdminRevokeKey:
    """DELETE /api/v1/admin/keys/{key_id}"""

    @pytest.mark.asyncio
    async def test_revoke_key_success(self, client, mock_db):
        """Admin can revoke an active API key."""
        async def override_admin():
            return _make_admin_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[admin_required] = override_admin
        app.dependency_overrides[get_db] = override_db

        from src.models.sql_models import ApiKey as ApiKeyModel

        key_id = uuid.uuid4()
        mock_key = MagicMock(spec=ApiKeyModel)
        mock_key.id = key_id
        mock_key.label = "test-key"
        mock_key.status = "active"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        try:
            response = await client.delete(f"/api/v1/admin/keys/{key_id}")
        finally:
            app.dependency_overrides.pop(admin_required, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert "revoked" in data["message"]
        # Key status should have been updated
        assert mock_key.status == "revoked"

    @pytest.mark.asyncio
    async def test_revoke_key_not_found(self, client, mock_db):
        """Revoking a non-existent key returns 404."""
        async def override_admin():
            return _make_admin_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[admin_required] = override_admin
        app.dependency_overrides[get_db] = override_db

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        try:
            response = await client.delete(f"/api/v1/admin/keys/{uuid.uuid4()}")
        finally:
            app.dependency_overrides.pop(admin_required, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_revoke_key_invalid_uuid(self, client, mock_db):
        """Invalid UUID returns 400."""
        async def override_admin():
            return _make_admin_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[admin_required] = override_admin
        app.dependency_overrides[get_db] = override_db

        try:
            response = await client.delete("/api/v1/admin/keys/not-a-uuid")
        finally:
            app.dependency_overrides.pop(admin_required, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_revoke_already_revoked_key(self, client, mock_db):
        """Revoking an already-revoked key returns success with message."""
        async def override_admin():
            return _make_admin_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[admin_required] = override_admin
        app.dependency_overrides[get_db] = override_db

        from src.models.sql_models import ApiKey as ApiKeyModel

        key_id = uuid.uuid4()
        mock_key = MagicMock(spec=ApiKeyModel)
        mock_key.id = key_id
        mock_key.label = "revoked-key"
        mock_key.status = "revoked"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)

        try:
            response = await client.delete(f"/api/v1/admin/keys/{key_id}")
        finally:
            app.dependency_overrides.pop(admin_required, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert "already revoked" in data["message"]


# ---------------------------------------------------------------------------
# User endpoints (non-admin)
# ---------------------------------------------------------------------------

class TestUserListKeys:
    """GET /api/v1/keys"""

    @pytest.mark.asyncio
    async def test_list_my_keys_success(self, client, mock_db):
        """Authenticated user can list their own keys."""
        async def override_user():
            return _make_regular_user()

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        from src.models.sql_models import ApiKey as ApiKeyModel
        from src.models.sql_models import User as UserModel

        user_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440002")
        key_id1 = uuid.uuid4()
        key_id2 = uuid.uuid4()

        mock_user = MagicMock(spec=UserModel)
        mock_user.id = user_uuid
        mock_user.email = "user@example.com"
        mock_user.role = "user"

        mock_key1 = MagicMock(spec=ApiKeyModel)
        mock_key1.id = key_id1
        mock_key1.user_id = user_uuid
        mock_key1.label = "key-1"
        mock_key1.tier = "hobby"
        mock_key1.rate_limit = 100
        mock_key1.status = "active"
        mock_key1.last_used_at = None
        mock_key1.created_at = None

        mock_key2 = MagicMock(spec=ApiKeyModel)
        mock_key2.id = key_id2
        mock_key2.user_id = user_uuid
        mock_key2.label = "key-2"
        mock_key2.tier = "pro"
        mock_key2.rate_limit = 500
        mock_key2.status = "active"
        mock_key2.last_used_at = None
        mock_key2.created_at = None

        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_key1, mock_user), (mock_key2, mock_user)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        try:
            response = await client.get("/api/v1/keys")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["label"] in ("key-1", "key-2")
        assert data[0]["user_email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_list_my_keys_requires_auth(self, client):
        """Unauthenticated user gets 401 or 403."""
        response = await client.get("/api/v1/keys")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Unit tests for key generation
# ---------------------------------------------------------------------------

class TestKeyGeneration:
    """Tests for API key generation and hashing."""

    def test_generate_api_key_format(self):
        from src.routers.keys import _generate_api_key

        key = _generate_api_key()
        assert key.startswith("kaf_")
        assert len(key) > 10
        # Should be URL-safe
        assert "/" not in key
        assert "+" not in key

    def test_hash_and_verify_api_key(self):
        from src.routers.keys import _generate_api_key, _hash_api_key
        from passlib.context import CryptContext

        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
        raw = _generate_api_key()
        hashed = _hash_api_key(raw)
        assert pwd.verify(raw, hashed)
        assert not pwd.verify("wrong-key", hashed)

    def test_unique_keys(self):
        from src.routers.keys import _generate_api_key

        keys = {_generate_api_key() for _ in range(20)}
        assert len(keys) == 20  # All unique
