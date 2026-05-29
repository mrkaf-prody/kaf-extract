"""Tests for Phase 4 payment system.

Covers:
- PaymentProvider abstract base + dispatcher
- Provider registry
- LemonSqueezy provider (checkout, webhook, cancel, signature)
- Paddle stub provider
- Manual payment provider + invoice generation
- Subscription router endpoints
- Webhook endpoint
"""

import json
import uuid
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
    mock_result.scalars = MagicMock()
    mock_result.scalars.return_value = []
    mock_result.scalars().first.return_value = return_value
    mock_result.scalars().all.return_value = [return_value] if return_value else []
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    return mock_result


# ---------------------------------------------------------------------------
# 1. Abstract base + dispatcher
# ---------------------------------------------------------------------------


class TestPaymentProviderBase:
    """Tests for the abstract PaymentProvider base class and dispatcher."""

    def test_cannot_instantiate_abstract(self):
        from src.services.payments.dispatcher import PaymentProvider

        with pytest.raises(TypeError):
            PaymentProvider()  # abstract

    def test_register_provider(self):
        from src.services.payments.dispatcher import (
            PaymentProvider,
            _provider_registry,
            register_provider,
        )

        # Should already have lemonsqueezy, paddle, manual registered
        assert "lemonsqueezy" in _provider_registry
        assert "paddle" in _provider_registry
        assert "manual" in _provider_registry

    def test_get_provider_returns_singleton(self):
        from src.services.payments.dispatcher import get_provider

        p1 = get_provider("manual")
        p2 = get_provider("manual")
        assert p1 is p2

    def test_get_provider_unknown_raises(self):
        from src.services.payments.dispatcher import get_provider

        with pytest.raises(ValueError, match="Unknown payment provider"):
            get_provider("nonexistent")

    def test_dispatcher_delegates(self):
        from src.services.payments.dispatcher import (
            PaymentDispatcher,
            get_provider,
        )

        provider = get_provider("manual")
        dispatcher = PaymentDispatcher("manual")
        assert dispatcher.provider is provider


# ---------------------------------------------------------------------------
# 2. LemonSqueezy provider
# ---------------------------------------------------------------------------


class TestLemonSqueezyProvider:
    """Tests for LemonSqueezy integration (mocked HTTP)."""

    @pytest.fixture
    def ls_provider(self):
        from src.services.payments.lemonsqueezy import LemonSqueezyProvider

        return LemonSqueezyProvider()

    @pytest.mark.asyncio
    async def test_create_checkout_success(self, ls_provider):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "id": "cs_test_123",
                "attributes": {"url": "https://checkout.lemonsqueezy.com/test"},
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            # Temporarily set a variant for the test
            with patch.object(
                ls_provider,
                "_plan_to_variant",
                return_value="var_test_456",
            ):
                result = await ls_provider.create_checkout(
                    user_id="user-123", plan="pro"
                )

        assert result["url"] == "https://checkout.lemonsqueezy.com/test"
        assert result["checkout_id"] == "cs_test_123"
        assert result["provider"] == "lemonsqueezy"

    @pytest.mark.asyncio
    async def test_create_checkout_no_variant_raises(self, ls_provider):
        with patch.object(
            ls_provider,
            "_plan_to_variant",
            side_effect=ValueError("No variant configured"),
        ):
            with pytest.raises(ValueError, match="No variant"):
                await ls_provider.create_checkout(user_id="u", plan="pro")

    @pytest.mark.asyncio
    async def test_handle_webhook_order_created(self, ls_provider):
        payload = {
            "meta": {"event_name": "order_created", "event_id": "evt_123"},
            "data": {
                "id": "order_123",
                "attributes": {
                    "customer": {"email": "test@example.com"},
                    "first_order_item": {"variant_id": 456},
                },
            },
        }
        headers = {"x-signature": "fake-sig"}

        # Mock signature verification to pass
        with patch.object(ls_provider, "verify_signature", return_value=True):
            result = await ls_provider.handle_webhook(payload, headers, raw_body=b"")

        assert result["event"] == "order_created"
        assert result["action"] == "order_created"
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_handle_webhook_subscription_updated(self, ls_provider):
        payload = {
            "meta": {"event_name": "subscription_updated", "event_id": "evt_456"},
            "data": {
                "id": "sub_789",
                "attributes": {
                    "status": "active",
                    "variant_id": "var_pro",
                    "renews_at": "2026-06-28",
                },
            },
        }
        headers = {"x-signature": "sig"}

        with patch.object(ls_provider, "verify_signature", return_value=True):
            # Map variant to plan
            with patch.dict(
                "src.services.payments.lemonsqueezy.VARIANT_PLAN_MAP",
                {"var_pro": "pro"},
            ):
                result = await ls_provider.handle_webhook(payload, headers, raw_body=b"")

        assert result["action"] == "subscription_updated"
        assert result["status"] == "active"
        assert result["plan"] == "pro"

    @pytest.mark.asyncio
    async def test_handle_webhook_bad_signature(self, ls_provider):
        payload = {"meta": {"event_name": "order_created"}, "data": {}}
        headers = {"x-signature": "bad"}

        with patch.object(ls_provider, "verify_signature", return_value=False):
            with pytest.raises(ValueError, match="Invalid webhook signature"):
                await ls_provider.handle_webhook(payload, headers, raw_body=b"")

    def test_verify_signature_valid(self, ls_provider):
        import hashlib
        import hmac

        secret = "test-secret"
        payload = b'{"test": true}'

        with patch.object(ls_provider, "_webhook_secret", secret):
            sig = hmac.new(
                secret.encode(), payload, hashlib.sha256
            ).hexdigest()
            result = ls_provider.verify_signature(payload, {"x-signature": sig})

        assert result is True

    def test_verify_signature_valid_str_payload(self, ls_provider):
        import hashlib
        import hmac

        secret = "test-secret"
        payload_str = '{"test": true}'

        with patch.object(ls_provider, "_webhook_secret", secret):
            sig = hmac.new(
                secret.encode(), payload_str.encode(), hashlib.sha256
            ).hexdigest()
            result = ls_provider.verify_signature(payload_str, {"x-signature": sig})

        assert result is True

    def test_verify_signature_invalid(self, ls_provider):
        with patch.object(ls_provider, "_webhook_secret", "test-secret"):
            result = ls_provider.verify_signature(b"{}", {"x-signature": "wrong"})

        assert result is False

    def test_verify_signature_no_secret_skips(self, ls_provider):
        with patch.object(ls_provider, "_webhook_secret", ""):
            result = ls_provider.verify_signature(b"{}", {"x-signature": "anything"})

        assert result is True

    @pytest.mark.asyncio
    async def test_handle_webhook_idempotency_dedup(self, ls_provider):
        """Same event_id should return dedup status on second call."""
        payload = {
            "meta": {"event_name": "order_created", "event_id": "evt_dup_1"},
            "data": {
                "id": "order_dup",
                "attributes": {
                    "customer": {"email": "dup@example.com"},
                    "first_order_item": {"variant_id": 999},
                },
            },
        }
        headers = {"x-signature": "fake"}

        with patch.object(ls_provider, "verify_signature", return_value=True):
            # Patch Redis so idempotency works without a real server
            from src.services.payments import webhooks as _wh_mod
            _seen = set()
            async def _is_processed(ev_id: str) -> bool:
                if ev_id in _seen:
                    return True
                _seen.add(ev_id)
                return False
            async def _mark_processed(ev_id: str, ttl: int = 86_400) -> None:
                _seen.add(ev_id)

            with patch.object(_wh_mod, "is_webhook_processed", _is_processed), \
                 patch.object(_wh_mod, "mark_webhook_processed", _mark_processed):

                # First call processes normally
                result1 = await ls_provider.handle_webhook(payload, headers, raw_body=b"")
                assert result1["status"] == "processed"

                # Second call with same event_id returns dedup
                result2 = await ls_provider.handle_webhook(payload, headers, raw_body=b"")
                assert result2["status"] == "dedup"
                assert result2["event_id"] == "evt_dup_1"

    @pytest.mark.asyncio
    async def test_handle_webhook_raw_body_signature(self, ls_provider):
        """Provider should verify signature against raw body, not re-serialised JSON."""
        import hashlib
        import hmac

        secret = "sig-secret"
        raw_body = b'{"meta":{"event_name":"order_created","event_id":"evt_raw"},"data":{"id":"o1"}}'
        sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

        payload = json.loads(raw_body)
        headers = {"x-signature": sig}

        with patch.object(ls_provider, "_webhook_secret", secret):
            result = await ls_provider.handle_webhook(payload, headers, raw_body=raw_body)

        assert result["status"] == "processed"
        assert result["event"] == "order_created"

    @pytest.mark.asyncio
    async def test_cancel_subscription(self, ls_provider):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = mock_response
            result = await ls_provider.cancel_subscription("sub_123")

        assert result["status"] == "canceled"
        assert result["subscription_id"] == "sub_123"

    @pytest.mark.asyncio
    async def test_get_subscription(self, ls_provider):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "sub_456",
                "attributes": {
                    "status": "active",
                    "variant_id": "var_pro",
                    "renews_at": "2026-07-01",
                },
            }
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await ls_provider.get_subscription("sub_456")

        assert result["subscription_id"] == "sub_456"
        assert result["status"] == "active"


# ---------------------------------------------------------------------------
# 3. Paddle stub provider
# ---------------------------------------------------------------------------


class TestPaddleStubProvider:
    """Tests for Paddle stub implementation."""

    @pytest.fixture
    def paddle_provider(self):
        from src.services.payments.paddle import PaddleProvider

        return PaddleProvider()

    @pytest.mark.asyncio
    async def test_create_checkout_stub(self, paddle_provider):
        result = await paddle_provider.create_checkout(
            user_id="user-1", plan="pro", email="test@test.com"
        )
        assert "url" in result
        assert result["provider"] == "paddle"
        assert "stub" in result.get("note", "")

    @pytest.mark.asyncio
    async def test_handle_webhook_stub(self, paddle_provider):
        payload = {"event_type": "subscription.activated", "data": {"id": "sub_1"}}
        result = await paddle_provider.handle_webhook(payload, {})
        assert result["event"] == "subscription.activated"
        assert result["status"] == "processed"

    @pytest.mark.asyncio
    async def test_cancel_subscription_stub(self, paddle_provider):
        result = await paddle_provider.cancel_subscription("sub_1")
        assert result["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_get_subscription_stub(self, paddle_provider):
        result = await paddle_provider.get_subscription("sub_1")
        assert result["subscription_id"] == "sub_1"

    def test_verify_signature_stub(self, paddle_provider):
        result = paddle_provider.verify_signature(b"{}", {})
        assert result is True


# ---------------------------------------------------------------------------
# 4. Manual payment provider + invoice generation
# ---------------------------------------------------------------------------


class TestManualPaymentProvider:
    """Tests for manual payment provider and invoice generation."""

    def test_generate_invoice_html(self):
        from src.services.payments.manual import generate_invoice_html

        html = generate_invoice_html(
            invoice_id="inv-test-001",
            customer_name="Test User",
            customer_email="test@example.com",
            plan="pro",
            amount_cents=2900,
            currency="usd",
            status="pending",
        )
        assert "Kaf Extract" in html
        assert "inv-test-001" in html
        assert "Test User" in html
        assert "test@example.com" in html
        assert "Pro" in html
        assert "$29.00" in html
        assert "PENDING" in html

    def test_generate_invoice_paid_status(self):
        from src.services.payments.manual import generate_invoice_html

        html = generate_invoice_html(
            invoice_id="inv-002",
            customer_name="Paid User",
            customer_email="paid@example.com",
            plan="enterprise",
            amount_cents=19900,
            status="paid",
        )
        assert "PAID" in html
        assert "Enterprise" in html
        assert "$199.00" in html

    @pytest.mark.asyncio
    async def test_create_checkout_manual(self):
        from src.services.payments.manual import ManualPaymentProvider

        provider = ManualPaymentProvider()
        result = await provider.create_checkout(user_id="u1", plan="pro")
        assert result["provider"] == "manual"
        assert "admin" in result.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_handle_webhook_manual_ignores(self):
        from src.services.payments.manual import ManualPaymentProvider

        provider = ManualPaymentProvider()
        result = await provider.handle_webhook({}, {})
        assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_save_invoice_creates_record(self, mock_db_session):
        from src.services.payments.manual import save_invoice

        user_id = uuid.uuid4()
        sub_id = uuid.uuid4()

        # Mock the invoices dir
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(settings, "invoices_dir", tmpdir):
                invoice = await save_invoice(
                    mock_db_session,
                    user_id=user_id,
                    subscription_id=sub_id,
                    plan="pro",
                    amount_cents=2900,
                    customer_name="Test",
                    customer_email="test@test.com",
                )

        # Verify db.add was called with an Invoice
        mock_db_session.add.assert_called()
        mock_db_session.flush.assert_called()


# ---------------------------------------------------------------------------
# 5. Subscription router endpoints (mocked DB)
# ---------------------------------------------------------------------------


class TestSubscriptionRouter:
    """Integration-style tests for subscription endpoints with mocked DB."""

    def _make_token(self, user_id="550e8400-e29b-41d4-a716-446655440000"):
        """Create a valid JWT for testing."""
        from src.middleware.auth import create_access_token

        return create_access_token(
            user_id=user_id,
            email="test@example.com",
            role="user",
        )

    @pytest.mark.asyncio
    async def test_get_my_subscription(self, client, mock_db_session):
        """GET /api/v1/subscriptions/me returns status."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        # Mock: no subscription, no trial
        _setup_mock_execute(mock_db_session, return_value=None)

        token = self._make_token()
        try:
            response = await client.get(
                "/api/v1/subscriptions/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert data["subscription"] is None
        assert data["trial"] is None
        assert "available_plans" in data
        assert len(data["available_plans"]) >= 1

    @pytest.mark.asyncio
    async def test_get_my_subscription_unauthorized(self, client):
        """GET /api/v1/subscriptions/me without auth fails."""
        response = await client.get("/api/v1/subscriptions/me")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_create_checkout_invalid_plan(self, client, mock_db_session):
        """POST /api/v1/subscriptions/checkout with bad plan fails."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db
        _setup_mock_execute(mock_db_session, return_value=None)

        token = self._make_token()
        try:
            response = await client.post(
                "/api/v1/subscriptions/checkout",
                json={"plan": "nonexistent_plan"},
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_checkout_manual(self, client, mock_db_session):
        """POST /api/v1/subscriptions/checkout via manual provider."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db

        # Mock user lookup to return a mock user
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        _setup_mock_execute(mock_db_session, return_value=mock_user)

        # Ensure manual provider is the active one
        with patch.object(settings, "payment_provider", "manual"):
            token = self._make_token()
            try:
                response = await client.post(
                    "/api/v1/subscriptions/checkout",
                    json={"plan": "pro"},
                    headers={"Authorization": f"Bearer {token}"},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "manual"
        assert data["plan"] == "pro"

    @pytest.mark.asyncio
    async def test_cancel_no_subscription(self, client, mock_db_session):
        """POST /api/v1/subscriptions/cancel without active sub fails."""
        async def override_get_db():
            yield mock_db_session

        app.dependency_overrides[get_db] = override_get_db
        _setup_mock_execute(mock_db_session, return_value=None)

        token = self._make_token()
        try:
            response = await client.post(
                "/api/v1/subscriptions/cancel",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 6. Webhook endpoint
# ---------------------------------------------------------------------------


class TestWebhookEndpoint:
    """Tests for the payment webhook endpoint."""

    @pytest.mark.asyncio
    async def test_webhook_receives_json(self, client):
        """POST /api/v1/webhooks/payment receives JSON payload."""
        # Manual provider just returns 'ignored'
        with patch.object(settings, "payment_provider", "manual"):
            response = await client.post(
                "/api/v1/webhooks/payment",
                json={"event": "test", "data": {}},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert data["provider"] == "manual"

    @pytest.mark.asyncio
    async def test_webhook_invalid_json(self, client):
        """POST /api/v1/webhooks/payment with bad JSON fails."""
        response = await client.post(
            "/api/v1/webhooks/payment",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# 7. Config
# ---------------------------------------------------------------------------


class TestPaymentConfig:
    """Tests that payment config defaults are sensible."""

    def test_default_provider_is_manual(self):
        assert settings.payment_provider == "manual"

    def test_plans_defined(self):
        assert "hobby" in settings.plans
        assert "pro" in settings.plans
        assert "enterprise" in settings.plans

    def test_hobby_is_free(self):
        assert settings.plans["hobby"]["price_cents"] == 0

    def test_trial_defaults(self):
        assert settings.trial_duration_days == 7
        assert settings.trial_extraction_limit == 100

    def test_invoices_dir_default(self):
        assert settings.invoices_dir == "/app/data/invoices"
