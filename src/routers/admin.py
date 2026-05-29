"""Admin dashboard API -- real data endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.auth import admin_required
from src.models.sql_models import Subscription, User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AdminSubscriptionItem(BaseModel):
    id: str
    user_email: str
    user_name: str | None
    plan: str
    status: str
    started_at: str | None
    expires_at: str | None
    provider: str


class AdminUserItem(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    status: str
    created_at: str


class AdminStatsResponse(BaseModel):
    total_users: int
    active_subscriptions: int
    api_calls_today: int
    error_rate_percent: float


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


@router.get("/subscriptions", response_model=list[AdminSubscriptionItem])
async def list_subscriptions(
    search: str = Query("", description="Filter by email or name"),
    status: str = Query("all", description="Filter by status"),
    plan: str = Query("all", description="Filter by plan"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """List all subscriptions with user details (admin only)."""
    query = (
        select(Subscription, User)
        .join(User, Subscription.user_id == User.id)
        .order_by(Subscription.created_at.desc())
    )

    if status != "all":
        query = query.where(Subscription.status == status)
    if plan != "all":
        query = query.where(Subscription.plan == plan)
    if search:
        query = query.where(
            (User.email.ilike(f"%{search}%")) | (User.name.ilike(f"%{search}%"))
        )

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)

    items = []
    for sub, user in result.all():
        items.append(
            AdminSubscriptionItem(
                id=str(sub.id),
                user_email=user.email,
                user_name=user.name,
                plan=sub.plan,
                status=sub.status,
                started_at=sub.current_period_start.isoformat() if sub.current_period_start else (sub.created_at.isoformat() if sub.created_at else None),
                expires_at=sub.current_period_end.isoformat() if sub.current_period_end else None,
                provider=sub.provider,
            )
        )
    return items


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[AdminUserItem])
async def list_users(
    search: str = Query("", description="Filter by email or name"),
    role: str = Query("all"),
    status: str = Query("all"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    query = select(User).order_by(User.created_at.desc())

    if role != "all":
        query = query.where(User.role == role)
    if status != "all":
        query = query.where(User.status == status)
    if search:
        query = query.where(
            (User.email.ilike(f"%{search}%")) | (User.name.ilike(f"%{search}%"))
        )

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)

    return [
        AdminUserItem(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=u.role,
            status=u.status,
            created_at=u.created_at.isoformat() if u.created_at else "",
        )
        for u in result.scalars().all()
    ]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Quick admin stats."""
    total_users = await db.scalar(select(func.count(User.id)))
    active_subs = await db.scalar(
        select(func.count(Subscription.id)).where(Subscription.status == "active")
    )

    try:
        from src.services.metrics import get_metrics
        m = get_metrics()
        calls_total = m.get("requests_total", 0) if "requests_total" in m else 0
        errors = m.get("error_count", 0) if "error_count" in m else 0
        error_rate = round((errors / calls_total) * 100, 2) if calls_total else 0.0
    except Exception:
        calls_total = 0
        error_rate = 0.0

    return {
        "total_users": total_users or 0,
        "active_subscriptions": active_subs or 0,
        "api_calls_today": calls_total,
        "error_rate_percent": error_rate,
    }
