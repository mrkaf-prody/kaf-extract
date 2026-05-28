"""Paddle payment provider (stub / backup integration).

Paddle Billing API: https://developer.paddle.com/api-reference/overview

This is a stub implementation that satisfies the PaymentProvider interface.
Full integration can be completed later by replacing the method bodies with
actual Paddle API calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from src.config import settings
from src.services.payments.dispatcher import PaymentProvider, register_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plan → Paddle price mapping
# ---------------------------------------------------------------------------

PLAN_PRICE_MAP: dict[str, str] = {
    "hobby": settings.paddle_price_hobby,
    "pro": settings.paddle_price_pro,
    "enterprise": settings.paddle_price_enterprise,
}

PRICE_PLAN_MAP: dict[str, str] = {
    v: k for k, v in PLAN_PRICE_MAP.items() if v
}


@register_provider
class PaddleProvider(PaymentProvider):
    """Paddle Billing payment provider (stub).

    Currently implements the interface with placeholder logic.
    Replace method bodies with real Paddle API calls for full integration.
    """

    name = "paddle"

    BASE_URL = "https://api.paddle.com"

    def __init__(self) -> None:
        self._api_key = settings.paddle_api_key
        self._webhook_secret = settings.paddle_webhook_secret
        self._test_mode = settings.paddle_test_mode

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _plan_to_price(self, plan: str) -> str:
        price_id = PLAN_PRICE_MAP.get(plan)
        if not price_id:
            raise ValueError(f"No Paddle price ID configured for plan '{plan}'")
        return price_id

    # ------------------------------------------------------------------
    # PaymentProvider interface
    # ------------------------------------------------------------------

    async def create_checkout(
        self,
        user_id: str,
        plan: str,
        *,
        email: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a Paddle checkout (stub).

        Full integration: POST /transactions with items → return checkout URL.
        """
        logger.info(
            "Paddle create_checkout called (STUB) for user=%s plan=%s", user_id, plan
        )

        # TODO(stub): Replace with real Paddle API call
        # price_id = self._plan_to_price(plan)
        # resp = await client.post(f"{self.BASE_URL}/transactions", ...)

        if not self._api_key:
            logger.warning(
                "PADDLE_API_KEY not set — returning stub checkout URL"
            )

        return {
            "url": f"https://checkout.paddle.com/checkout/stub?plan={plan}&user={user_id}",
            "provider": "paddle",
            "note": "Paddle integration is in stub mode. Set PADDLE_API_KEY for production.",
        }

    async def handle_webhook(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """Process Paddle webhook (stub)."""
        logger.info("Paddle handle_webhook called (STUB)")

        # Verify signature
        if not self._webhook_secret:
            logger.warning("PADDLE_WEBHOOK_SECRET not set — skipping verification")

        event_type = payload.get("event_type", "unknown")
        data = payload.get("data", {})

        result = {
            "status": "processed",
            "event": event_type,
            "provider": "paddle",
            "note": "Stub — full integration needed",
        }

        if event_type == "subscription.activated":
            result["action"] = "subscription_activated"
            result["subscription_id"] = data.get("id")

        elif event_type == "subscription.canceled":
            result["action"] = "subscription_canceled"
            result["subscription_id"] = data.get("id")

        elif event_type == "subscription.updated":
            result["action"] = "subscription_updated"
            result["subscription_id"] = data.get("id")

        elif event_type == "transaction.completed":
            result["action"] = "transaction_completed"
            result["transaction_id"] = data.get("id")

        return result

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Cancel a Paddle subscription (stub)."""
        logger.info("Paddle cancel_subscription called (STUB) for %s", subscription_id)

        # TODO(stub): POST /subscriptions/{id}/cancel

        return {
            "status": "canceled",
            "subscription_id": subscription_id,
            "provider": "paddle",
            "note": "Stub — full integration needed",
        }

    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Retrieve a Paddle subscription (stub)."""
        logger.info("Paddle get_subscription called (STUB) for %s", subscription_id)

        # TODO(stub): GET /subscriptions/{id}

        return {
            "subscription_id": subscription_id,
            "status": "active",
            "provider": "paddle",
            "note": "Stub — full integration needed",
        }

    def verify_signature(
        self, payload: bytes | str, headers: dict[str, str]
    ) -> bool:
        """Verify Paddle webhook signature (stub).

        Paddle uses asymmetric key verification (Paddle signs with their
        private key, you verify with the public key from the Paddle dashboard).
        Full implementation: fetch public key, verify JWT/signature.
        """
        secret = self._webhook_secret
        if not secret:
            logger.warning("PADDLE_WEBHOOK_SECRET not set — skipping verification")
            return True

        # TODO(stub): Implement proper Paddle signature verification
        # Paddle v2 uses notification settings with a secret for HMAC
        # or RSA public key verification
        return True
