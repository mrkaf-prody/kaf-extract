"""Tests for Phase 4 voucher system.

Covers:
- Voucher SQLAlchemy models
- VoucherService (generate, redeem, list, export, invalidate)
- Voucher router endpoints (admin + user-facing)
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.config import settings
from src.main import app
from src.db import get_db


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
def mock_db_session():
    """Create a mock async DB session with common methods."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = AsyncMock()
    session.delete = AsyncMock()
    return session


def _setup_mock_execute(mock_db_session, return_value=None):
    """Helper: mock db.execute to return a result with scalar_one_or_none()."""
    mock_scalar = AsyncMock(return_value=return_value)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_scalar()

    # For scalars().first() and scalars().all() — need proper nesting
    mock_scalars_chain = MagicMock()
    mock_scalars_chain.first.return_value = return_value
    mock_scalars_chain.all.return_value = [return_value] if return_value else []
    mock_result.scalars.return_value = mock_scalars_chain
    mock_result.scalar.return_value = 0  # for count queries
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    return mock_result


def _make_admin_token(user_id="550e8400-e29b-41d4-a716-446655440000"):
    """Create a valid admin JWT for testing."""
    from src.middleware.auth import create_access_token
    return create_access_token(
        user_id=user_id,
        email="admin@example.com",
        role="admin",
    )


def _make_user_token(user_id="550e8400-e29b-41d4-a716-446655440001"):
    """Create a valid user JWT for testing."""
    from src.middleware.auth import create_access_token
    return create_access_token(
        user_id=user_id,
        email="user@example.com",
        role="user",
    )


# ---------------------------------------------------------------------------
# 1. Voucher model tests
# ---------------------------------------------------------------------------


class TestVoucherModel:
    """Tests for Voucher and VoucherRedemption SQLAlchemy models."""

    def test_voucher_creation(self):
        from src.models.sql_models import Voucher

        now = datetime.now(UTC)
        expiry = now + timedelta(days=30)
        v = Voucher(
            id=uuid.uuid4(),
            code="KAF-TEST-ABCD",
            plan="pro",
            duration_days=30,
            extraction_credits=100,
            expires_at=expiry,
            max_uses=1,
            used_count=0,
            status="active",
        )
        assert v.code == "KAF-TEST-ABCD"
        assert v.plan == "pro"
        assert v.duration_days == 30
        assert v.extraction_credits == 100
        assert v.status == "active"
        assert repr(v) is not None

    def test_voucher_redemption_creation(self):
        from src.models.sql_models import VoucherRedemption

        vid = uuid.uuid4()
        uid = uuid.uuid4()
        r = VoucherRedemption(
            id=uuid.uuid4(),
            voucher_id=vid,
            user_id=uid,
            ip_address="127.0.0.1",
        )
        assert r.voucher_id == vid
        assert r.user_id == uid
        assert r.ip_address == "127.0.0.1"
        assert repr(r) is not None

    def test_voucher_defaults(self):
        from src.models.sql_models import Voucher

        expiry = datetime.now(UTC) + timedelta(days=365)
        v = Voucher(
            id=uuid.uuid4(),
            code="DEFAULT-TEST",
            plan="hobby",
            expires_at=expiry,
        )
        assert v.duration_days == 30
        assert v.extraction_credits == 0
        assert v.max_uses == 1
        assert v.used_count == 0
        assert v.status == "active"


# ---------------------------------------------------------------------------
# 2. VoucherService tests
# ---------------------------------------------------------------------------


class TestVoucherService:
    """Tests for VoucherService business logic."""

    @pytest.fixture
    def service(self):
        from src.services.vouchers import VoucherService
        return VoucherService()

    # --- Code generation ---

    def test_generate_code_format(self):
        from src.services.vouchers import _generate_code

        code = _generate_code("KAF")
        assert code.startswith("KAF-")
        # Should have two blocks: KAF-XXXX-XXXX or KAF-XXXXXX
        parts = code.split("-")
        assert len(parts) >= 2
        assert all(len(p) > 0 for p in parts)

    # --- Batch generation ---

    @pytest.mark.asyncio
    async def test_generate_batch_creates_vouchers(self, service, mock_db_session):
        # Mock: no existing codes in DB
        _setup_mock_execute(mock_db_session, return_value=None)

        vouchers = await service.generate_batch(
            mock_db_session,
            plan="pro",
            quantity=5,
            duration_days=30,
            prefix="KAF",
        )

        assert len(vouchers) == 5
        for v in vouchers:
            assert v.code.startswith("KAF-")
            assert v.plan == "pro"
            assert v.status == "active"
            assert v.duration_days == 30
        # db.add should have been called 5 times
        assert mock_db_session.add.call_count == 5

    @pytest.mark.asyncio
    async def test_generate_batch_invalid_plan(self, service, mock_db_session):
        _setup_mock_execute(mock_db_session, return_value=None)

        with patch.object(settings, "plans", {"hobby": {}, "pro": {}, "enterprise": {}}):
            with pytest.raises(ValueError, match="Invalid plan"):
                await service.generate_batch(
                    mock_db_session,
                    plan="nonexistent",
                    quantity=1,
                )

    @pytest.mark.asyncio
    async def test_generate_batch_invalid_quantity(self, service, mock_db_session):
        with pytest.raises(ValueError, match="between 1 and 500"):
            await service.generate_batch(
                mock_db_session,
                plan="pro",
                quantity=0,
            )

        with pytest.raises(ValueError, match="between 1 and 500"):
            await service.generate_batch(
                mock_db_session,
                plan="pro",
                quantity=501,
            )

    # --- Redemption ---

    @pytest.mark.asyncio
    async def test_redeem_voucher_success(self, service, mock_db_session):
        from src.models.sql_models import Voucher, User

        user_id = uuid.uuid4()
        voucher_id = uuid.uuid4()
        expiry = datetime.now(UTC) + timedelta(days=30)

        voucher = Voucher(
            id=voucher_id,
            code="KAF-TEST-1234",
            plan="pro",
            duration_days=30,
            extraction_credits=50,
            expires_at=expiry,
            max_uses=1,
            used_count=0,
            status="active",
        )

        user = User(
            id=user_id,
            email="test@example.com",
            password_hash="hash",
            role="user",
            status="active",
        )

        # Mock: voucher lookup returns voucher, user lookup returns user,
        # redemption lookup returns None (not already redeemed)
        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            mock_result = AsyncMock()
            if call_count[0] == 1:
                # Voucher lookup
                mock_result.scalar_one_or_none.return_value = voucher
            elif call_count[0] == 2:
                # Existing redemption check
                mock_result.scalar_one_or_none.return_value = None
            elif call_count[0] == 3:
                # User lookup
                mock_result.scalar_one_or_none.return_value = user
            return mock_result

        mock_db_session.execute = mock_execute

        result = await service.redeem_voucher(
            mock_db_session,
            user_id=user_id,
            code="KAF-TEST-1234",
            ip_address="192.168.1.1",
        )

        assert result["plan"] == "pro"
        assert result["duration_days"] == 30
        assert result["extraction_credits"] == 50
        assert "subscription_id" in result
        assert "period_end" in result

        # Voucher should now have used_count=1 and status "exhausted"
        assert voucher.used_count == 1
        assert voucher.status == "exhausted"

    @pytest.mark.asyncio
    async def test_redeem_voucher_not_found(self, service, mock_db_session):
        _setup_mock_execute(mock_db_session, return_value=None)

        with pytest.raises(ValueError, match="Invalid voucher code"):
            await service.redeem_voucher(
                mock_db_session,
                user_id=uuid.uuid4(),
                code="NONEXISTENT",
            )

    @pytest.mark.asyncio
    async def test_redeem_voucher_expired(self, service, mock_db_session):
        from src.models.sql_models import Voucher

        voucher_id = uuid.uuid4()
        expiry = datetime.now(UTC) - timedelta(days=1)  # expired yesterday

        voucher = Voucher(
            id=voucher_id,
            code="KAF-OLD-CODE",
            plan="pro",
            duration_days=30,
            expires_at=expiry,
            max_uses=1,
            used_count=0,
            status="active",
        )

        _setup_mock_execute(mock_db_session, return_value=voucher)

        with pytest.raises(ValueError, match="expired"):
            await service.redeem_voucher(
                mock_db_session,
                user_id=uuid.uuid4(),
                code="KAF-OLD-CODE",
            )

    @pytest.mark.asyncio
    async def test_redeem_voucher_revoked(self, service, mock_db_session):
        from src.models.sql_models import Voucher

        voucher_id = uuid.uuid4()
        expiry = datetime.now(UTC) + timedelta(days=30)

        voucher = Voucher(
            id=voucher_id,
            code="KAF-REVOKED",
            plan="pro",
            duration_days=30,
            expires_at=expiry,
            max_uses=1,
            used_count=0,
            status="revoked",
        )

        _setup_mock_execute(mock_db_session, return_value=voucher)

        with pytest.raises(ValueError, match="revoked"):
            await service.redeem_voucher(
                mock_db_session,
                user_id=uuid.uuid4(),
                code="KAF-REVOKED",
            )

    @pytest.mark.asyncio
    async def test_redeem_voucher_exhausted(self, service, mock_db_session):
        from src.models.sql_models import Voucher

        voucher_id = uuid.uuid4()
        expiry = datetime.now(UTC) + timedelta(days=30)

        voucher = Voucher(
            id=voucher_id,
            code="KAF-USED",
            plan="pro",
            duration_days=30,
            expires_at=expiry,
            max_uses=1,
            used_count=1,
            status="exhausted",
        )

        _setup_mock_execute(mock_db_session, return_value=voucher)

        with pytest.raises(ValueError, match="maximum uses"):
            await service.redeem_voucher(
                mock_db_session,
                user_id=uuid.uuid4(),
                code="KAF-USED",
            )

    # --- Invalidation ---

    @pytest.mark.asyncio
    async def test_invalidate_voucher(self, service, mock_db_session):
        from src.models.sql_models import Voucher

        voucher_id = uuid.uuid4()
        expiry = datetime.now(UTC) + timedelta(days=30)
        voucher = Voucher(
            id=voucher_id,
            code="KAF-TO-KILL",
            plan="pro",
            duration_days=30,
            expires_at=expiry,
            status="active",
        )

        _setup_mock_execute(mock_db_session, return_value=voucher)

        result = await service.invalidate_voucher(mock_db_session, voucher_id)
        assert result.status == "revoked"

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent(self, service, mock_db_session):
        _setup_mock_execute(mock_db_session, return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await service.invalidate_voucher(mock_db_session, uuid.uuid4())

    # --- CSV export ---

    @pytest.mark.asyncio
    async def test_export_unused_csv(self, service, mock_db_session):
        from src.models.sql_models import Voucher

        v1 = Voucher(
            id=uuid.uuid4(), code="KAF-AAAA", plan="pro",
            duration_days=30, expires_at=datetime.now(UTC) + timedelta(days=30),
            status="active", max_uses=1, used_count=0,
        )
        v2 = Voucher(
            id=uuid.uuid4(), code="KAF-BBBB", plan="hobby",
            duration_days=60, expires_at=datetime.now(UTC) + timedelta(days=60),
            status="active", max_uses=5, used_count=2,
        )

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [v1, v2]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        csv = await service.export_unused_csv(mock_db_session)

        assert "KAF-AAAA" in csv
        assert "KAF-BBBB" in csv
        assert "Code,Plan,DurationDays" in csv

    # --- List vouchers ---

    @pytest.mark.asyncio
    async def test_list_vouchers(self, service, mock_db_session):
        from src.models.sql_models import Voucher

        v1 = Voucher(
            id=uuid.uuid4(), code="KAF-L1", plan="pro",
            duration_days=30, expires_at=datetime.now(UTC) + timedelta(days=30),
            status="active", max_uses=1, used_count=0,
        )
        v2 = Voucher(
            id=uuid.uuid4(), code="KAF-L2", plan="enterprise",
            duration_days=90, expires_at=datetime.now(UTC) + timedelta(days=90),
            status="active", max_uses=10, used_count=0,
        )

        # Mock count + data queries
        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            mr = AsyncMock()
            if call_count[0] == 1:
                # Count query
                mr.scalar.return_value = 2
            else:
                # Data query
                mr.scalars.return_value.all.return_value = [v1, v2]
            return mr

        mock_db_session.execute = mock_execute

        vouchers, total = await service.list_vouchers(mock_db_session)
        assert total == 2
        assert len(vouchers) == 2
        assert vouchers[0].code in ("KAF-L1", "KAF-L2")


# ---------------------------------------------------------------------------
# 3. Voucher router endpoint tests (mocked DB)
# ---------------------------------------------------------------------------


class TestVoucherRouter:
    """Integration-style tests for voucher endpoints with mocked DB."""

    @pytest.mark.asyncio
    async def test_list_vouchers_admin(self, client, mock_db_session):
        """GET /api/v1/admin/vouchers returns voucher list."""
        from src.models.sql_models import Voucher

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        v1 = Voucher(
            id=uuid.uuid4(), code="KAF-R1", plan="pro",
            duration_days=30, expires_at=datetime.now(UTC) + timedelta(days=30),
            status="active", max_uses=1, used_count=0,
        )

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            mr = AsyncMock()
            if call_count[0] == 1:
                mr.scalar.return_value = 1
            else:
                mr.scalars.return_value.all.return_value = [v1]
            return mr

        mock_db_session.execute = mock_execute

        token = _make_admin_token()
        try:
            response = await client.get(
                "/api/v1/admin/vouchers",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["vouchers"]) == 1
        assert data["vouchers"][0]["code"] == "KAF-R1"

    @pytest.mark.asyncio
    async def test_list_vouchers_requires_admin(self, client, mock_db_session):
        """Non-admin user cannot list vouchers."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db
        _setup_mock_execute(mock_db_session, return_value=None)

        token = _make_user_token()
        try:
            response = await client.get(
                "/api/v1/admin/vouchers",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_generate_vouchers_admin(self, client, mock_db_session):
        """POST /api/v1/admin/vouchers/generate creates vouchers."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        # Mock no existing codes
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        token = _make_admin_token()
        try:
            response = await client.post(
                "/api/v1/admin/vouchers/generate",
                json={"plan": "pro", "quantity": 3, "duration_days": 30},
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 201
        data = response.json()
        assert data["plan"] == "pro"
        assert data["quantity"] == 3
        assert len(data["codes"]) == 3
        for code in data["codes"]:
            assert code.startswith("KAF-")

    @pytest.mark.asyncio
    async def test_generate_vouchers_requires_admin(self, client, mock_db_session):
        """Non-admin cannot generate vouchers."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db
        _setup_mock_execute(mock_db_session, return_value=None)

        token = _make_user_token()
        try:
            response = await client.post(
                "/api/v1/admin/vouchers/generate",
                json={"plan": "pro", "quantity": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invalidate_voucher_admin(self, client, mock_db_session):
        """DELETE /api/v1/admin/vouchers/{id} invalidates a voucher."""
        from src.models.sql_models import Voucher

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        vid = uuid.uuid4()
        voucher = Voucher(
            id=vid, code="KAF-KILL", plan="pro",
            duration_days=30, expires_at=datetime.now(UTC) + timedelta(days=30),
            status="active", max_uses=1, used_count=0,
        )
        _setup_mock_execute(mock_db_session, return_value=voucher)

        token = _make_admin_token()
        try:
            response = await client.delete(
                f"/api/v1/admin/vouchers/{vid}",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "revoked"

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_voucher(self, client, mock_db_session):
        """DELETE returns 404 for nonexistent voucher."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db
        _setup_mock_execute(mock_db_session, return_value=None)

        token = _make_admin_token()
        try:
            response = await client.delete(
                f"/api/v1/admin/vouchers/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_export_csv_admin(self, client, mock_db_session):
        """GET /api/v1/admin/vouchers/export returns CSV."""
        from src.models.sql_models import Voucher

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        v1 = Voucher(
            id=uuid.uuid4(), code="KAF-EXP1", plan="pro",
            duration_days=30, expires_at=datetime.now(UTC) + timedelta(days=30),
            status="active", max_uses=1, used_count=0,
        )

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [v1]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        token = _make_admin_token()
        try:
            response = await client.get(
                "/api/v1/admin/vouchers/export",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        assert "KAF-EXP1" in response.text
        assert "text/csv" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_redeem_voucher_user(self, client, mock_db_session):
        """POST /api/v1/vouchers/redeem activates a subscription."""
        from src.models.sql_models import User, Voucher

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        user_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440001")
        voucher_id = uuid.uuid4()
        expiry = datetime.now(UTC) + timedelta(days=30)

        voucher = Voucher(
            id=voucher_id, code="KAF-MYCODE", plan="hobby",
            duration_days=30, extraction_credits=0,
            expires_at=expiry, max_uses=1, used_count=0, status="active",
        )
        user = User(
            id=user_id, email="user@example.com", password_hash="h",
            role="user", status="active",
        )

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            mr = AsyncMock()
            if call_count[0] == 1:
                mr.scalar_one_or_none.return_value = voucher
            elif call_count[0] == 2:
                mr.scalar_one_or_none.return_value = None  # no prior redemption
            elif call_count[0] == 3:
                mr.scalar_one_or_none.return_value = user
            else:
                mr.scalar_one_or_none.return_value = None
            return mr

        mock_db_session.execute = mock_execute

        token = _make_user_token()
        try:
            response = await client.post(
                "/api/v1/vouchers/redeem",
                json={"code": "KAF-MYCODE"},
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "hobby"
        assert "subscription_id" in data

    @pytest.mark.asyncio
    async def test_redeem_requires_auth(self, client):
        """POST /api/v1/vouchers/redeem without auth fails."""
        response = await client.post(
            "/api/v1/vouchers/redeem",
            json={"code": "SOME-CODE"},
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_redemption_history(self, client, mock_db_session):
        """GET /api/v1/vouchers/history returns user's redemptions."""
        from src.models.sql_models import Voucher, VoucherRedemption

        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        user_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440001")
        expiry = datetime.now(UTC) + timedelta(days=30)
        voucher = Voucher(
            id=uuid.uuid4(), code="KAF-HIST1", plan="pro",
            duration_days=30, expires_at=expiry,
            status="active", max_uses=1, used_count=0,
        )
        redemption = VoucherRedemption(
            id=uuid.uuid4(), voucher_id=voucher.id, user_id=user_id,
            ip_address="10.0.0.1",
        )
        redemption.voucher = voucher  # simulate relationship

        call_count = [0]

        async def mock_execute(stmt):
            call_count[0] += 1
            mr = AsyncMock()
            if call_count[0] == 1:
                mr.scalar.return_value = 1
            else:
                mr.scalars.return_value.all.return_value = [redemption]
            return mr

        mock_db_session.execute = mock_execute

        token = _make_user_token()
        try:
            response = await client.get(
                "/api/v1/vouchers/history",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["redemptions"]) == 1
        assert data["redemptions"][0]["voucher_code"] == "KAF-HIST1"


# ---------------------------------------------------------------------------
# 4. Admin payments router tests
# ---------------------------------------------------------------------------


class TestAdminPaymentsRouter:
    """Tests for admin payments configuration endpoints."""

    @pytest.mark.asyncio
    async def test_get_payment_config(self, client, mock_db_session):
        """GET /api/v1/admin/payments returns config."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        token = _make_admin_token()
        try:
            response = await client.get(
                "/api/v1/admin/payments",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert "active_provider" in data
        assert "test_mode" in data
        assert "providers" in data
        for p in ["lemonsqueezy", "paddle", "stripe", "manual"]:
            assert p in data["providers"]

    @pytest.mark.asyncio
    async def test_get_payment_config_requires_admin(self, client, mock_db_session):
        """Non-admin cannot access payment config."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        token = _make_user_token()
        try:
            response = await client.get(
                "/api/v1/admin/payments",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_patch_payment_config(self, client, mock_db_session):
        """PATCH /api/v1/admin/payments updates config."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        token = _make_admin_token()
        try:
            response = await client.patch(
                "/api/v1/admin/payments",
                json={
                    "active_provider": "stripe",
                    "test_mode": True,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert "active_provider" in data
