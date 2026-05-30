"""Subscription router — user subscription management."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db
from src.middleware.auth import get_current_user
from src.models.sql_models import Subscription, Trial, User
from src.services.plans import get_plans, validate_plan_key
from src.services.payments import get_provider
from src.services.payments.dispatcher import PaymentDispatcher

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    plan: str = "pro"
    success_url: str = ""
    cancel_url: str = ""


class CheckoutResponse(BaseModel):
    checkout_url: str
    provider: str
    plan: str
    message: str | None = None


class SubscriptionResponse(BaseModel):
    id: str
    plan: str
    status: str
    provider: str
    current_period_start: str | None = None
    current_period_end: str | None = None
    created_at: str


class TrialInfo(BaseModel):
    status: str
    extractions_total: int
    extractions_used: int
    extractions_remaining: int
    started_at: str
    expires_at: str
    days_left: int


class SubscriptionStatusResponse(BaseModel):
    subscription: SubscriptionResponse | None = None
    trial: TrialInfo | None = None
    available_plans: list[dict[str, Any]]


class CancelResponse(BaseModel):
    message: str
    status: str


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sub_to_response(sub: Subscription) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=str(sub.id),
        plan=sub.plan,
        status=sub.status,
        provider=sub.provider,
        current_period_start=sub.current_period_start.isoformat()
        if sub.current_period_start
        else None,
        current_period_end=sub.current_period_end.isoformat()
        if sub.current_period_end
        else None,
        created_at=sub.created_at.isoformat() if sub.created_at else "",
    )


def _trial_to_response(trial: Trial) -> TrialInfo:
    now = datetime.now(UTC)
    days_left = max(0, (trial.expires_at - now).days) if trial.expires_at else 0
    return TrialInfo(
        status=trial.status,
        extractions_total=trial.extractions_total,
        extractions_used=trial.extractions_used,
        extractions_remaining=trial.extractions_remaining,
        started_at=trial.started_at.isoformat() if trial.started_at else "",
        expires_at=trial.expires_at.isoformat() if trial.expires_at else "",
        days_left=days_left,
    )


async def _get_active_subscription(
    db: AsyncSession, user_id: uuid.UUID
) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/me", response_model=SubscriptionStatusResponse)
async def get_my_subscription(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's subscription status, trial info, and plans."""
    user_id = current_user["user_id"]

    # Active subscription
    sub = await _get_active_subscription(db, user_id)

    # Trial
    result = await db.execute(select(Trial).where(Trial.user_id == user_id))
    trial = result.scalar_one_or_none()

    # Available plans
    plans_list = await get_plans(db)

    return SubscriptionStatusResponse(
        subscription=_sub_to_response(sub) if sub else None,
        trial=_trial_to_response(trial) if trial else None,
        available_plans=plans_list,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a checkout session with the active payment provider."""
    user_id = current_user["user_id"]

    # Validate plan
    if not await validate_plan_key(db, body.plan):
        plans = await get_plans(db)
        valid_keys = [p["key"] for p in plans]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan '{body.plan}'. Choose: {valid_keys}",
        )

    # Get user email for checkout
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    # Get plan details from DB
    from src.services.plans import get_plan_by_key
    plan = await get_plan_by_key(db, body.plan)

    # --- Free Plan: auto-activate, no payment needed ---
    if plan and plan["price_cents"] == 0:
        from datetime import UTC, datetime as dt
        from src.models.sql_models import Subscription

        # Cancel any existing active subscription
        existing = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id, Subscription.status == "active"
            )
        )
        for sub in existing.scalars():
            sub.status = "canceled"
            sub.canceled_at = dt.now(UTC)

        # Create free subscription
        new_sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            plan=body.plan,
            status="active",
            provider="manual",
        )
        db.add(new_sub)
        await db.flush()

        return CheckoutResponse(
            checkout_url="",
            provider="manual",
            plan=body.plan,
            message=f"{plan['name']} plan activated — free forever. Start extracting!",
        )

    # --- Paid plans: use payment provider ---
    dispatcher = PaymentDispatcher()
    try:
        checkout = await dispatcher.create_checkout(
            user_id=str(user_id),
            plan=body.plan,
            email=user.email if user else "",
            name=user.name if user and user.name else "",
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment provider error: {str(e)}",
        )

    return CheckoutResponse(
        checkout_url=checkout.get("url", ""),
        provider=checkout.get("provider", settings.payment_provider),
        plan=body.plan,
        message=checkout.get("message"),
    )


@router.post("/cancel", response_model=CancelResponse)
async def cancel_subscription(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel the current user's active subscription."""
    user_id = current_user["user_id"]

    sub = await _get_active_subscription(db, user_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    # Cancel at the provider if applicable
    if sub.provider_subscription_id and sub.provider != "manual":
        dispatcher = PaymentDispatcher()
        try:
            await dispatcher.cancel_subscription(sub.provider_subscription_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Provider cancel failed: {str(e)}",
            )

    # Mark canceled in DB
    sub.status = "canceled"
    sub.canceled_at = datetime.now(UTC)
    await db.flush()

    return CancelResponse(
        message="Subscription canceled successfully",
        status="canceled",
    )
