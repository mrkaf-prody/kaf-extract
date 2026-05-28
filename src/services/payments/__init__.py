"""Payment services package."""

from src.services.payments.dispatcher import (
    PaymentDispatcher,
    PaymentProvider,
    get_provider,
    register_provider,
)

# Import providers so they self-register when the package is loaded
from src.services.payments import lemonsqueezy  # noqa: F401
from src.services.payments import manual  # noqa: F401
from src.services.payments import paddle  # noqa: F401

__all__ = [
    "PaymentDispatcher",
    "PaymentProvider",
    "get_provider",
    "register_provider",
]
