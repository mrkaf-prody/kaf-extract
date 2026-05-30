"""Plans service — reads plans from database with config fallback.

This module provides a single source of truth for plan data.
When the database has plans, it uses those.
When the database is empty (first boot), it falls back to config.py.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sql_models import Plan

logger = logging.getLogger(__name__)


async def get_plans_from_db(db: AsyncSession) -> list[dict[str, Any]]:
    """Get all active plans from the database.

    Returns a list of plan dicts with keys:
    - key, name, description, price_cents, currency, billing_period,
      extractions_per_month, is_active, sort_order
    - features: list of feature flag keys assigned to this plan
    """
    from src.models.sql_models import FeatureFlag, PlanFeatureLink

    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order, Plan.key)  # noqa: E712
    )
    plans = result.scalars().all()

    if not plans:
        return []

    plan_list = []
    for plan in plans:
        # Get features assigned to this plan
        feat_result = await db.execute(
            select(FeatureFlag.key)
            .join(PlanFeatureLink, PlanFeatureLink.feature_id == FeatureFlag.id)
            .where(PlanFeatureLink.plan_id == plan.id)
        )
        feature_keys = [row[0] for row in feat_result.all()]

        plan_list.append({
            "key": plan.key,
            "name": plan.name,
            "description": plan.description,
            "price_cents": plan.price_cents,
            "currency": plan.currency,
            "billing_period": plan.billing_period,
            "extractions_per_month": plan.extractions_per_month,
            "features": feature_keys,
        })

    return plan_list


def get_plans_from_config() -> list[dict[str, Any]]:
    """Fallback: get plans from config.py (hardcoded)."""
    from src.config import settings

    plan_list = []
    for plan_key, plan_info in settings.plans.items():
        plan_list.append({
            "key": plan_key,
            "name": plan_info["name"],
            "description": None,
            "price_cents": plan_info["price_cents"],
            "currency": "USD",
            "billing_period": "monthly",
            "extractions_per_month": plan_info["extractions_per_month"],
            "features": plan_info.get("features", []),
        })
    return plan_list


async def get_plans(db: AsyncSession) -> list[dict[str, Any]]:
    """Get plans — DB first, config fallback."""
    plans = await get_plans_from_db(db)
    if plans:
        return plans
    return get_plans_from_config()


async def get_plan_by_key(db: AsyncSession, plan_key: str) -> dict[str, Any] | None:
    """Get a single plan by key."""
    plans = await get_plans(db)
    for plan in plans:
        if plan["key"] == plan_key:
            return plan
    return None


async def validate_plan_key(db: AsyncSession, plan_key: str) -> bool:
    """Check if a plan key is valid."""
    plan = await get_plan_by_key(db, plan_key)
    return plan is not None
