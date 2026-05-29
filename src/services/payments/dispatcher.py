"""Payment provider dispatcher — routes to the active payment provider."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class PaymentProvider(ABC):
    """Abstract base for all payment providers.

    Every provider must implement these five methods. The signatures use
    generic dicts / keyword arguments so each provider can accept whatever
    payload shape its upstream API requires.
    """

    name: str = "base"

    @abstractmethod
    async def create_checkout(
        self, user_id: str, plan: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Create a checkout session / payment link.

        Returns a dict with at least: {"url": "https://checkout.example.com/..."}
        """
        ...

    @abstractmethod
    async def handle_webhook(
        self, payload: dict[str, Any], headers: dict[str, str], *, raw_body: bytes | str = b""
    ) -> dict[str, Any]:
        """Process an incoming webhook event from the provider.

        Must verify the webhook signature before processing.
        Returns a dict with at least: {"status": "processed", "event": "..."}
        """
        ...

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Cancel an active subscription at the provider."""
        ...

    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Retrieve subscription details from the provider."""
        ...

    @abstractmethod
    def verify_signature(
        self, payload: bytes | str, headers: dict[str, str]
    ) -> bool:
        """Cryptographically verify the webhook payload came from the provider."""
        ...


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_provider_registry: dict[str, type[PaymentProvider]] = {}
_provider_instances: dict[str, PaymentProvider] = {}


def register_provider(cls: type[PaymentProvider]) -> type[PaymentProvider]:
    """Decorator / manual call to register a PaymentProvider implementation."""
    if not hasattr(cls, "name") or not cls.name:
        raise ValueError(f"Provider class {cls.__name__} must define a 'name' attribute")
    _provider_registry[cls.name] = cls
    logger.info("Registered payment provider: %s", cls.name)
    return cls


def get_provider(name: str | None = None) -> PaymentProvider:
    """Return a singleton instance of the named (or default) provider."""
    provider_name = name or settings.payment_provider
    if provider_name in _provider_instances:
        return _provider_instances[provider_name]

    cls = _provider_registry.get(provider_name)
    if cls is None:
        msg = (
            f"Unknown payment provider '{provider_name}'. "
            f"Available: {list(_provider_registry)}"
        )
        logger.error(msg)
        raise ValueError(msg)

    instance = cls()
    _provider_instances[provider_name] = instance
    return instance


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class PaymentDispatcher:
    """Convenience class that delegates to the active provider."""

    def __init__(self, provider_name: str | None = None) -> None:
        self._provider = get_provider(provider_name)

    @property
    def provider(self) -> PaymentProvider:
        return self._provider

    async def create_checkout(self, user_id: str, plan: str, **kwargs: Any) -> dict[str, Any]:
        return await self._provider.create_checkout(user_id, plan, **kwargs)

    async def handle_webhook(
        self, payload: dict[str, Any], headers: dict[str, str], *, raw_body: bytes | str = b""
    ) -> dict[str, Any]:
        return await self._provider.handle_webhook(payload, headers, raw_body=raw_body)

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        return await self._provider.cancel_subscription(subscription_id)

    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        return await self._provider.get_subscription(subscription_id)

    async def verify_signature(
        self, payload: bytes | str, headers: dict[str, str]
    ) -> bool:
        return self._provider.verify_signature(payload, headers)
