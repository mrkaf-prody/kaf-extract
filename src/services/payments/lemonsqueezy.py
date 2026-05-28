"""LemonSqueezy payment provider integration.

LemonSqueezy is a merchant-of-record platform that handles tax/VAT globally.
API docs: https://docs.lemonsqueezy.com/api
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from src.config import settings
from src.services.payments.dispatcher import PaymentProvider, register_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plan → variant mapping
# ---------------------------------------------------------------------------

PLAN_VARIANT_MAP: dict[str, str] = {
    "hobby": settings.lemonsqueezy_variant_hobby,
    "pro": settings.lemonsqueezy_variant_pro,
    "enterprise": settings.lemonsqueezy_variant_enterprise,
}

# Reverse map: variant_id → plan
VARIANT_PLAN_MAP: dict[str, str] = {
    v: k for k, v in PLAN_VARIANT_MAP.items() if v
}

# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


@register_provider
class LemonSqueezyProvider(PaymentProvider):
    """LemonSqueezy payment provider.

    Supports subscriptions via Store > Products > Variants.
    """

    name = "lemonsqueezy"

    BASE_URL = "https://api.lemonsqueezy.com/v1"

    def __init__(self) -> None:
        self._api_key = settings.lemonsqueezy_api_key
        self._store_id = settings.lemonsqueezy_store_id
        self._webhook_secret = settings.lemonsqueezy_webhook_secret
        self._test_mode = settings.lemonsqueezy_test_mode

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def _plan_to_variant(self, plan: str) -> str:
        variant = PLAN_VARIANT_MAP.get(plan)
        if not variant:
            raise ValueError(
                f"No LemonSqueezy variant configured for plan '{plan}'. "
                f"Set LEMONSQUEEZY_VARIANT_{plan.upper()} env var."
            )
        return variant

    def _variant_to_plan(self, variant_id: str) -> str | None:
        return VARIANT_PLAN_MAP.get(variant_id)

    # ------------------------------------------------------------------
    # PaymentProvider interface
    # ------------------------------------------------------------------

    async def create_checkout(
        self,
        user_id: str,
        plan: str,
        *,
        email: str = "",
        name: str = "",
        success_url: str = "",
        cancel_url: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a LemonSqueezy checkout for the given plan.

        Returns a dict with 'url' (the checkout URL) and 'checkout_id'.
        """
        variant_id = self._plan_to_variant(plan)

        checkout_data: dict[str, Any] = {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {
                    "custom": {
                        "user_id": str(user_id),
                        "plan": plan,
                    }
                },
                "product_options": {
                    "enabled_variants": [variant_id],
                },
            },
            "relationships": {
                "store": {
                    "data": {
                        "type": "stores",
                        "id": self._store_id,
                    }
                },
                "variant": {
                    "data": {
                        "type": "variants",
                        "id": variant_id,
                    }
                },
            },
        }

        if email:
            checkout_data["attributes"]["checkout_data"]["email"] = email
        if name:
            checkout_data["attributes"]["checkout_data"]["name"] = name
        if success_url:
            checkout_data["attributes"]["checkout_data"]["success_url"] = success_url
        if cancel_url:
            checkout_data["attributes"]["checkout_data"]["cancel_url"] = cancel_url

        if self._test_mode:
            checkout_data["attributes"]["test_mode"] = True

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/checkouts",
                json={"data": checkout_data},
                headers=self._headers(),
            )

        if resp.status_code not in (200, 201):
            logger.error(
                "LemonSqueezy checkout creation failed: %s %s",
                resp.status_code,
                resp.text[:500],
            )
            raise RuntimeError(f"LemonSqueezy checkout failed: {resp.text[:300]}")

        data = resp.json()
        checkout_url = data["data"]["attributes"]["url"]
        checkout_id = data["data"]["id"]

        logger.info(
            "Created LemonSqueezy checkout %s for user %s plan %s",
            checkout_id,
            user_id,
            plan,
        )

        return {
            "url": checkout_url,
            "checkout_id": checkout_id,
            "provider": "lemonsqueezy",
        }

    async def handle_webhook(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """Process LemonSqueezy webhook events.

        Supported events: order_created, subscription_updated,
        subscription_cancelled, subscription_expired.
        """
        # Verify signature
        raw_body = json.dumps(payload) if isinstance(payload, dict) else str(payload)
        sig_header = headers.get("x-signature", "")
        if not self.verify_signature(raw_body, headers):
            logger.warning("LemonSqueezy webhook signature verification failed")
            raise ValueError("Invalid webhook signature")

        event_name = payload.get("meta", {}).get("event_name", "")
        data = payload.get("data", {})
        attrs = data.get("attributes", {})

        logger.info("LemonSqueezy webhook event: %s", event_name)

        result = {"status": "processed", "event": event_name, "provider": "lemonsqueezy"}

        if event_name == "order_created":
            result["action"] = "order_created"
            result["order_id"] = data.get("id")
            # Customer details from the order
            cust_data = attrs.get("customer", {})
            result["email"] = cust_data.get("email", "")
            # Find variant/plan from first order item
            first_item = attrs.get("first_order_item", {})
            variant_id = str(first_item.get("variant_id", ""))
            result["plan"] = self._variant_to_plan(variant_id)

        elif event_name in ("subscription_updated", "subscription_created"):
            result["action"] = "subscription_updated"
            sub_id = data.get("id")
            result["subscription_id"] = str(sub_id)
            result["status"] = attrs.get("status", "active")
            result["plan"] = self._variant_to_plan(
                str(attrs.get("variant_id", ""))
            )
            result["renews_at"] = attrs.get("renews_at")
            result["ends_at"] = attrs.get("ends_at")

        elif event_name == "subscription_cancelled":
            result["action"] = "subscription_cancelled"
            result["subscription_id"] = str(data.get("id"))

        elif event_name == "subscription_expired":
            result["action"] = "subscription_expired"
            result["subscription_id"] = str(data.get("id"))

        else:
            result["action"] = "unknown"
            logger.info("Unhandled LemonSqueezy event: %s", event_name)

        return result

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Cancel a LemonSqueezy subscription."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.BASE_URL}/subscriptions/{subscription_id}",
                headers=self._headers(),
            )

        if resp.status_code not in (200, 204):
            logger.error(
                "LemonSqueezy cancel failed: %s %s",
                resp.status_code,
                resp.text[:300],
            )
            raise RuntimeError(f"Cancel failed: {resp.text[:200]}")

        return {
            "status": "canceled",
            "subscription_id": subscription_id,
            "provider": "lemonsqueezy",
        }

    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Retrieve a LemonSqueezy subscription."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/subscriptions/{subscription_id}",
                headers=self._headers(),
            )

        if resp.status_code != 200:
            raise RuntimeError(f"Get subscription failed: {resp.text[:200]}")

        data = resp.json()["data"]
        attrs = data["attributes"]

        return {
            "subscription_id": data["id"],
            "status": attrs.get("status"),
            "plan": self._variant_to_plan(str(attrs.get("variant_id", ""))),
            "renews_at": attrs.get("renews_at"),
            "ends_at": attrs.get("ends_at"),
            "created_at": attrs.get("created_at"),
            "provider": "lemonsqueezy",
        }

    def verify_signature(
        self, payload: bytes | str, headers: dict[str, str]
    ) -> bool:
        """Verify LemonSqueezy HMAC-SHA256 signature.

        LemonSqueezy signs the raw request body with the webhook secret.
        The signature is in the X-Signature header.
        """
        secret = self._webhook_secret
        if not secret:
            logger.warning("No LEMONSQUEEZY_WEBHOOK_SECRET set; skipping signature check")
            return True  # In development, skip if not configured

        signature = headers.get("x-signature", "")
        if not signature:
            return False

        if isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        else:
            payload_bytes = payload

        computed = hmac.new(
            secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed, signature)


# ---------------------------------------------------------------------------
# Helper for manual testing / admin calls
# ---------------------------------------------------------------------------

def get_lemonsqueezy_provider() -> LemonSqueezyProvider:
    """Return a LemonSqueezy provider instance directly (bypasses dispatcher)."""
    return LemonSqueezyProvider()
