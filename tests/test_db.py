"""Tests for database models and session management."""

import uuid
from datetime import UTC, datetime

import pytest


class TestSqlModels:
    """Tests for SQLAlchemy ORM model definitions."""

    def test_user_model_creation(self):
        """Verify User model can be instantiated with required fields."""
        from src.models.sql_models import User

        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash="$2b$hashed",
            role="user",
            status="active",
        )
        assert user.email == "test@example.com"
        assert user.role == "user"
        assert user.status == "active"
        assert isinstance(user.id, uuid.UUID)

    def test_api_key_model_creation(self):
        """Verify ApiKey model can be instantiated."""
        from src.models.sql_models import ApiKey

        user_id = uuid.uuid4()
        key = ApiKey(
            id=uuid.uuid4(),
            user_id=user_id,
            key_hash="$2b$hashed",
            label="my-key",
            tier="pro",
            rate_limit=500,
            status="active",
        )
        assert key.label == "my-key"
        assert key.tier == "pro"
        assert key.rate_limit == 500
        assert key.status == "active"
        assert key.user_id == user_id

    def test_refresh_token_model_creation(self):
        """Verify RefreshToken model can be instantiated."""
        from src.models.sql_models import RefreshToken

        user_id = uuid.uuid4()
        expires = datetime(2026, 1, 1, tzinfo=UTC)
        rt = RefreshToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash="$2b$hashed",
            expires_at=expires,
        )
        assert rt.user_id == user_id
        assert rt.expires_at == expires

    def test_usage_log_model_creation(self):
        """Verify UsageLog model can be instantiated."""
        from src.models.sql_models import UsageLog

        api_key_id = uuid.uuid4()
        log = UsageLog(
            id=uuid.uuid4(),
            api_key_id=api_key_id,
            endpoint="/api/v1/extract",
            url="https://example.com",
            duration_ms=250,
            status="200",
        )
        assert log.endpoint == "/api/v1/extract"
        assert log.duration_ms == 250
        assert log.status == "200"

    def test_all_tables_registered_in_base(self):
        """Verify all expected tables are in the Base metadata."""
        from src.models.sql_models import Base

        table_names = {t.name for t in Base.metadata.sorted_tables}
        assert "users" in table_names
        assert "api_keys" in table_names
        assert "refresh_tokens" in table_names
        assert "usage_logs" in table_names


class TestDatabaseModule:
    """Tests for src/db session management."""

    def test_get_db_is_async_generator(self):
        """Verify get_db is an async generator function."""
        from inspect import isasyncgenfunction
        from src.db import get_db

        assert isasyncgenfunction(get_db)


class TestConfig:
    """Tests for updated configuration."""

    def test_database_url_defaults_to_postgres(self):
        """Verify default database_url is PostgreSQL."""
        from src.config import settings
        assert "postgresql+asyncpg" in settings.database_url

    def test_jwt_settings_exist(self):
        """Verify JWT settings are available."""
        from src.config import settings
        assert settings.jwt_secret
        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_expire_minutes > 0
        assert settings.jwt_refresh_expire_days > 0


class TestApiKeyModule:
    """Tests for the database-backed API key module."""

    def test_verify_dev_key_sync(self):
        """Verify the dev API key works via sync verification."""
        from src.models.apikey import verify_api_key_sync

        result = verify_api_key_sync("kaf-extract-dev-key-change-in-production")
        assert result is not None
        assert result["label"] == "dev-default"
        assert result["rate_limit"] == 100

    def test_verify_invalid_key_sync(self):
        """Verify an invalid key returns None."""
        from src.models.apikey import verify_api_key_sync

        result = verify_api_key_sync("completely-invalid-key-12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_dev_key_async(self):
        """Verify the dev API key works via async verification."""
        from src.models.apikey import verify_api_key

        result = await verify_api_key("kaf-extract-dev-key-change-in-production")
        assert result is not None
        assert result["label"] == "dev-default"

    @pytest.mark.asyncio
    async def test_verify_invalid_key_async(self):
        """Verify an invalid key returns None (async)."""
        from src.models.apikey import verify_api_key

        result = await verify_api_key("completely-invalid-key-12345")
        assert result is None


class TestAuthMiddleware:
    """Tests for auth middleware functions."""

    def test_create_access_token_format(self):
        """Access token should be a 3-part JWT string."""
        from src.middleware.auth import create_access_token

        token = create_access_token(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            role="user",
        )
        parts = token.split(".")
        assert len(parts) == 3  # header.payload.signature

    def test_decode_token_type(self):
        """Decoded token should have expected type field."""
        from src.middleware.auth import create_access_token, decode_token

        token = create_access_token(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            role="admin",
        )
        payload = decode_token(token)
        assert payload["type"] == "access"
        assert payload["role"] == "admin"
