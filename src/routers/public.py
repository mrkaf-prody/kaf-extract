"""Public API endpoints — no auth required. Used by landing page."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db
from src.models.sql_models import FeatureFlag

router = APIRouter(prefix="/api/v1/public", tags=["public"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PublicPlan(BaseModel):
    key: str
    name: str
    price_cents: int
    price_display: str
    billing_period: str
    extractions_per_month: int
    features: list[str]
    highlight: bool


class PublicFeature(BaseModel):
    key: str
    name: str
    description: str | None = None
    category: str


# ---------------------------------------------------------------------------
# Feature categories for landing page grouping
# ---------------------------------------------------------------------------

_FEATURE_CATEGORIES: dict[str, str] = {
    "css_extraction": "Core Extraction",
    "ai_extraction": "Core Extraction",
    "markdown_extraction": "Core Extraction",
    "screenshot_capture": "Core Extraction",
    "batch_extraction": "Core Extraction",
    "async_extraction": "Core Extraction",
    "webhook_callbacks": "Core Extraction",
    "scheduled_extractions": "Automation",
    "csv_export": "Export",
    "slack_integration": "Integrations",
    "api_access": "Developer",
    "python_sdk": "Developer",
    "javascript_sdk": "Developer",
    "api_docs": "Developer",
    "two_factor_auth": "Security",
    "organizations": "Collaboration",
    "trial_system": "Billing",
    "voucher_system": "Billing",
    "invoice_generation": "Billing",
    "extraction_history": "Dashboard",
    "usage_dashboard": "Dashboard",
    "admin_analytics": "Admin",
}

_HIGHLIGHT_PLANS = {"pro"}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=list[PublicPlan])
async def public_plans():
    """Return active plans for landing page pricing section."""
    plans = []
    for plan_key, plan_info in settings.plans.items():
        price_cents = plan_info["price_cents"]
        if price_cents == 0:
            price_display = "Free"
        else:
            price_display = f"${price_cents / 100:.0f}"

        plans.append(
            PublicPlan(
                key=plan_key,
                name=plan_info["name"],
                price_cents=price_cents,
                price_display=price_display,
                billing_period="month",
                extractions_per_month=plan_info["extractions_per_month"],
                features=plan_info["features"],
                highlight=plan_key in _HIGHLIGHT_PLANS,
            )
        )
    return plans


@router.get("/features", response_model=list[PublicFeature])
async def public_features(
    db: AsyncSession = Depends(get_db),
):
    """Return enabled features for landing page feature grid."""
    result = await db.execute(
        select(FeatureFlag)
        .where(FeatureFlag.default_enabled == True)
        .order_by(FeatureFlag.key)
    )
    flags = result.scalars().all()
    return [
        PublicFeature(
            key=f.key,
            name=f.name,
            description=f.description,
            category=_FEATURE_CATEGORIES.get(f.key, "Other"),
        )
        for f in flags
    ]
