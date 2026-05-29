"""Admin payments router — provider configuration management."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.auth import admin_required

router = APIRouter(prefix="/api/v1/admin/payments", tags=["admin-payments"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProviderConfig(BaseModel):
    api_key: str = ""
    webhook_secret: str = ""
    enabled: bool = True


class PaymentConfigResponse(BaseModel):
    active_provider: str
    test_mode: bool
    providers: dict[str, ProviderConfig]


class PaymentConfigUpdate(BaseModel):
    active_provider: str | None = None
    test_mode: bool | None = None
    providers: dict[str, ProviderConfig] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=PaymentConfigResponse)
async def get_payment_config(
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Get current payment provider configuration (admin only).

    Returns the active provider, test mode status, and provider API keys
    (masked for security).
    """
    from src.config import settings
    import os

    providers = {}
    for key in ["lemonsqueezy", "paddle", "stripe", "manual"]:
        api_key_env = os.getenv(f"PAYMENT_{key.upper()}_API_KEY", "")
        webhook_env = os.getenv(f"PAYMENT_{key.upper()}_WEBHOOK_SECRET", "")

        # Mask keys if they exist
        masked_key = ""
        if api_key_env:
            if len(api_key_env) > 8:
                masked_key = api_key_env[:4] + "•" * (len(api_key_env) - 8) + api_key_env[-4:]
            else:
                masked_key = "•" * len(api_key_env)

        masked_webhook = ""
        if webhook_env:
            if len(webhook_env) > 8:
                masked_webhook = webhook_env[:5] + "•" * (len(webhook_env) - 10) + webhook_env[-5:]
            else:
                masked_webhook = "•" * len(webhook_env)

        providers[key] = ProviderConfig(
            api_key=masked_key or "",
            webhook_secret=masked_webhook or "",
            enabled=bool(api_key_env) or key == "manual",  # manual is always enabled
        )

    return PaymentConfigResponse(
        active_provider=settings.payment_provider,
        test_mode=settings.lemonsqueezy_test_mode,
        providers=providers,
    )


@router.patch("", response_model=PaymentConfigResponse)
async def update_payment_config(
    body: PaymentConfigUpdate,
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Update payment provider configuration (admin only)."""
    import os

    if body.active_provider is not None:
        os.environ["PAYMENT_PROVIDER"] = body.active_provider
        # Also update the settings object
        from src.config import settings
        settings.payment_provider = body.active_provider

    if body.test_mode is not None:
        os.environ["PAYMENT_TEST_MODE"] = str(body.test_mode).lower()
        # Update runtime settings so provider singletons see the change
        from src.config import settings
        settings.lemonsqueezy_test_mode = body.test_mode
        settings.paddle_test_mode = body.test_mode

    if body.providers is not None:
        for key, cfg in body.providers.items():
            key_upper = key.upper()
            # Only update if the value doesn't look masked (contains "•")
            if cfg.api_key and "•" not in cfg.api_key:
                os.environ[f"PAYMENT_{key_upper}_API_KEY"] = cfg.api_key
            if cfg.webhook_secret and "•" not in cfg.webhook_secret:
                os.environ[f"PAYMENT_{key_upper}_WEBHOOK_SECRET"] = cfg.webhook_secret

    # Return updated config
    return await get_payment_config(admin=admin, db=db)
