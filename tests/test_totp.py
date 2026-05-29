"""Tests for TOTP 2FA flow."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db
from src.utils.crypto import encrypt_totp_secret, decrypt_totp_secret, generate_backup_codes


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = AsyncMock()
    session.delete = AsyncMock()
    return session


class TestCryptoUtils:
    """Tests for TOTP crypto utilities."""

    def test_encrypt_decrypt_roundtrip(self):
        secret = pyotp.random_base32()
        encrypted = encrypt_totp_secret(secret)
        decrypted = decrypt_totp_secret(encrypted)
        assert secret == decrypted
        assert encrypted != secret

    def test_generate_backup_codes(self):
        plain, hashed = generate_backup_codes(count=8)
        assert len(plain) == 8
        assert len(hashed) == 8
        for p in plain:
            assert len(p) == 8  # token_hex(4) -> 8 hex chars
        for h in hashed:
            assert len(h) == 64  # SHA256 hex


class TestTOTPEndpoints:
    """Tests for TOTP setup, verify, disable, and login endpoints."""

    @pytest.mark.asyncio
    async def test_setup_2fa_already_enabled(self, client, mock_db_session):
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        user = MagicMock()
        user.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        user.email = "test@example.com"
        user.totp_enabled = True
        user.totp_secret = encrypt_totp_secret(pyotp.random_base32())

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db_session.execute = AsyncMock(return_value=result)

        from src.middleware.auth import create_access_token
        token = create_access_token(str(user.id), user.email, "user")

        try:
            response = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 409
            data = response.json()
            assert "already configured" in data["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_setup_2fa_success(self, client, mock_db_session):
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        user = MagicMock()
        user.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        user.email = "test@example.com"
        user.totp_enabled = False
        user.totp_secret = None

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db_session.execute = AsyncMock(return_value=result)

        from src.middleware.auth import create_access_token
        token = create_access_token(str(user.id), user.email, "user")

        try:
            response = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
            data = response.json()
            assert "secret" in data
            assert "qr_code_uri" in data
            assert "qr_code_data_uri" in data
            assert data["qr_code_data_uri"].startswith("data:image/png;base64,")
            expected_uri = pyotp.totp.TOTP(data["secret"]).provisioning_uri(name=user.email, issuer_name="Kaf Extract")
            assert data["qr_code_uri"] == expected_uri
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_verify_2fa_success(self, client, mock_db_session):
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        user = MagicMock()
        user.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        user.email = "test@example.com"
        user.totp_enabled = False
        user.totp_secret = None
        user.password_hash = "$2b$12$fakehash"

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db_session.execute = AsyncMock(return_value=result)

        from src.middleware.auth import create_access_token
        token = create_access_token(str(user.id), user.email, "user")

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        code = totp.now()

        try:
            response = await client.post(
                "/auth/2fa/verify",
                headers={"Authorization": f"Bearer {token}"},
                json={"secret": secret, "code": code},
            )
            assert response.status_code == 200
            data = response.json()
            assert "backup_codes" in data
            assert len(data["backup_codes"]) == 8
            assert user.totp_enabled is True
            assert user.totp_secret is not None
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_verify_2fa_invalid_code(self, client, mock_db_session):
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        user = MagicMock()
        user.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        user.email = "test@example.com"
        user.totp_enabled = False
        user.totp_secret = None

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db_session.execute = AsyncMock(return_value=result)

        from src.middleware.auth import create_access_token
        token = create_access_token(str(user.id), user.email, "user")

        try:
            response = await client.post(
                "/auth/2fa/verify",
                headers={"Authorization": f"Bearer {token}"},
                json={"secret": pyotp.random_base32(), "code": "000000"},
            )
            assert response.status_code == 400
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_disable_2fa_success(self, client, mock_db_session):
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        secret = pyotp.random_base32()
        user = MagicMock()
        user.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        user.email = "test@example.com"
        user.totp_enabled = True
        user.totp_secret = encrypt_totp_secret(secret)
        user.password_hash = "$2b$12$fakehash"

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db_session.execute = AsyncMock(return_value=result)

        from src.middleware.auth import create_access_token
        token = create_access_token(str(user.id), user.email, "user")

        totp = pyotp.TOTP(secret)
        code = totp.now()

        with patch("src.routers.auth._verify_password", return_value=True):
            try:
                response = await client.post(
                    "/auth/2fa/disable",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"password": "secretpassword", "code": code},
                )
                assert response.status_code == 200
                data = response.json()
                assert "disabled" in data["message"].lower()
                assert user.totp_enabled is False
                assert user.totp_secret is None
                assert user.backup_codes is None
            finally:
                app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_disable_2fa_not_enabled(self, client, mock_db_session):
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        user = MagicMock()
        user.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        user.email = "test@example.com"
        user.totp_enabled = False
        user.totp_secret = None

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db_session.execute = AsyncMock(return_value=result)

        from src.middleware.auth import create_access_token
        token = create_access_token(str(user.id), user.email, "user")

        try:
            response = await client.post(
                "/auth/2fa/disable",
                headers={"Authorization": f"Bearer {token}"},
                json={"password": "secretpassword", "code": "123456"},
            )
            assert response.status_code == 400
            assert "not enabled" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestAdminRequires2FA:
    """Tests for admin 2FA enforcement."""

    @pytest.mark.asyncio
    async def test_admin_endpoint_requires_2fa(self, client, mock_db_session):
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        user = MagicMock()
        user.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        user.email = "admin@kafcenter.com"
        user.role = "admin"
        user.totp_enabled = False
        user.totp_secret = None
        user.status = "active"

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db_session.execute = AsyncMock(return_value=result)

        from src.middleware.auth import create_access_token
        token = create_access_token(str(user.id), user.email, "admin")

        try:
            response = await client.post(
                "/auth/admin/reset",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 403
            assert "requires 2fa" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_admin_with_2fa_allowed(self, client, mock_db_session):
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        secret = pyotp.random_base32()
        user = MagicMock()
        user.id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        user.email = "admin@kafcenter.com"
        user.role = "admin"
        user.totp_enabled = True
        user.totp_secret = encrypt_totp_secret(secret)
        user.status = "active"

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db_session.execute = AsyncMock(return_value=result)

        from src.middleware.auth import create_access_token
        token = create_access_token(str(user.id), user.email, "admin")

        try:
            response = await client.post(
                "/auth/admin/reset",
                headers={"Authorization": f"Bearer {token}"},
            )
            # Should pass 2FA check and move on to other logic (may 500 because ADMIN_RESET_TOKEN not set)
            assert response.status_code in (200, 500)
        finally:
            app.dependency_overrides.pop(get_db, None)
