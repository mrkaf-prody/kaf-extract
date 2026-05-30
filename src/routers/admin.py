"""Admin dashboard API -- real data endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.auth import admin_required
from src.models.sql_models import AuditLog, FeatureFlag, Subscription, User, UserFeatureOverride

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


class PaginatedUsersResponse(BaseModel):
    users: list[AdminUserItem]
    total: int


class AdminStatsResponse(BaseModel):
    total_users: int
    active_subscriptions: int
    api_calls_today: int
    error_rate_percent: float


class MessageResponse(BaseModel):
    message: str


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


@router.get("/users", response_model=PaginatedUsersResponse)
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

    # Count total matching users
    count_query = select(func.count(User.id))
    if search:
        count_query = count_query.where(
            (User.email.ilike(f"%{search}%")) | (User.name.ilike(f"%{search}%"))
        )
    if role != "all":
        count_query = count_query.where(User.role == role)
    if status != "all":
        count_query = count_query.where(User.status == status)
    total = await db.scalar(count_query) or 0

    return {
        "users": [
            AdminUserItem(
                id=str(u.id),
                email=u.email,
                name=u.name,
                role=u.role,
                status=u.status,
                created_at=u.created_at.isoformat() if u.created_at else "",
            )
            for u in result.scalars().all()
        ],
        "total": total,
    }


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: str,
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a user by setting status to 'deleted' (admin only)."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id UUID format",
        )

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.status = "deleted"
    await db.flush()

    return MessageResponse(message=f"User '{user.email}' has been deleted")


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str | None = None
    role: str = Field(default="user")


@router.post("/users", response_model=AdminUserItem, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: CreateUserRequest,
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user from the admin panel (admin only)."""
    from src.utils.bcrypt_utils import hash_password
    # Check email exists
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
        role=body.role,
        status="active",
    )
    db.add(user)
    await db.flush()
    return AdminUserItem(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        status=user.status,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.get("/users/{user_id}", response_model=AdminUserItem)
async def get_user(
    user_id: str,
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Get a single user by ID (admin only)."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id UUID format",
        )
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return AdminUserItem(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        status=user.status,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


class AdminUpdateUserRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    status: str | None = None


@router.patch("/users/{user_id}", response_model=AdminUserItem)
async def admin_update_user(
    user_id: str,
    body: AdminUpdateUserRequest,
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's name, role, or status from the admin panel."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id UUID format",
        )
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role
    if body.status is not None:
        user.status = body.status
    await db.flush()
    return AdminUserItem(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        status=user.status,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


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


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------


class UpdateSubscriptionRequest(BaseModel):
    plan: str | None = None
    status: str | None = None


@router.patch("/subscriptions/{subscription_id}", response_model=AdminSubscriptionItem)
async def update_subscription(
    subscription_id: str,
    body: UpdateSubscriptionRequest,
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Update a subscription's plan or status (admin only)."""
    try:
        sid = uuid.UUID(subscription_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription_id UUID format",
        )

    result = await db.execute(
        select(Subscription, User)
        .join(User, Subscription.user_id == User.id)
        .where(Subscription.id == sid)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    sub, user = row

    if body.plan:
        sub.plan = body.plan
    if body.status:
        sub.status = body.status

    await db.flush()

    return AdminSubscriptionItem(
        id=str(sub.id),
        user_email=user.email,
        user_name=user.name,
        plan=sub.plan,
        status=sub.status,
        started_at=sub.current_period_start.isoformat() if sub.current_period_start else (sub.created_at.isoformat() if sub.created_at else None),
        expires_at=sub.current_period_end.isoformat() if sub.current_period_end else None,
        provider=sub.provider,
    )


@router.post("/subscriptions/{subscription_id}/cancel", response_model=AdminSubscriptionItem)
async def cancel_subscription(
    subscription_id: str,
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a subscription by setting status to 'canceled' (admin only)."""
    try:
        sid = uuid.UUID(subscription_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription_id UUID format",
        )

    result = await db.execute(
        select(Subscription, User)
        .join(User, Subscription.user_id == User.id)
        .where(Subscription.id == sid)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    sub, user = row

    sub.status = "canceled"
    sub.canceled_at = datetime.now(UTC)
    await db.flush()

    return AdminSubscriptionItem(
        id=str(sub.id),
        user_email=user.email,
        user_name=user.name,
        plan=sub.plan,
        status=sub.status,
        started_at=sub.current_period_start.isoformat() if sub.current_period_start else (sub.created_at.isoformat() if sub.created_at else None),
        expires_at=sub.current_period_end.isoformat() if sub.current_period_end else None,
        provider=sub.provider,
    )



# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get("/analytics")
async def admin_analytics(
    range: str = Query("30d", regex="^(7d|30d|90d)$"),
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Aggregate analytics for the admin dashboard."""
    try:
        from datetime import timedelta

        days = {"7d": 7, "30d": 30, "90d": 90}.get(range, 30)
        since = datetime.now(UTC) - timedelta(days=days)

        # Signups per day
        result = await db.execute(
            select(func.date_trunc("day", User.created_at), func.count(User.id))
            .where(User.created_at >= since)
            .group_by(func.date_trunc("day", User.created_at))
            .order_by(func.date_trunc("day", User.created_at))
        )
        signups_per_day = [
            {"date": d.isoformat() if hasattr(d, "isoformat") else str(d), "count": c}
            for d, c in result.all()
        ]

        # MRR by plan
        result = await db.execute(
            select(Subscription.plan, func.count(Subscription.id))
            .where(Subscription.status == "active")
            .group_by(Subscription.plan)
        )
        plan_counts = {plan: count for plan, count in result.all()}
        plan_prices = {"hobby": 0, "pro": 2900, "enterprise": 9900}
        mrr = sum(plan_counts.get(p, 0) * plan_prices[p] for p in plan_prices)
        revenue_by_plan = [
            {"plan": p, "count": plan_counts.get(p, 0), "mrr": plan_counts.get(p, 0) * plan_prices[p]}
            for p in plan_prices
        ]

        # Total users, active subscriptions
        total_users = await db.scalar(select(func.count(User.id)))
        total_subs = await db.scalar(
            select(func.count(Subscription.id)).where(Subscription.status == "active")
        )

        # Churn = canceled in period / total at start of period
        canceled = await db.scalar(
            select(func.count(Subscription.id))
            .where(Subscription.status == "canceled", Subscription.canceled_at >= since)
        )
        churn_rate = round((canceled / max(total_subs, 1)) * 100, 2) if total_subs else 0.0

        # ARPU
        arpu = round(mrr / max(total_subs, 1), 2) if total_subs else 0.0

        return {
            "range": range,
            "mrr_cents": mrr,
            "arpu_cents": arpu,
            "churn_rate_percent": churn_rate,
            "total_users": total_users or 0,
            "active_subscriptions": total_subs or 0,
            "signups_per_day": signups_per_day,
            "revenue_by_plan": revenue_by_plan,
        }
    except Exception:
        # Return safe defaults if analytics queries fail (e.g., missing columns)
        import logging
        logging.getLogger("admin.analytics").exception("Analytics query failed")
        return {
            "range": range,
            "mrr_cents": 0,
            "arpu_cents": 0,
            "churn_rate_percent": 0.0,
            "total_users": 0,
            "active_subscriptions": 0,
            "signups_per_day": [],
            "revenue_by_plan": [],
        }


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------


class AuditLogItem(BaseModel):
    id: str
    action: str
    target_type: str
    target_id: str
    details: str | None = None
    admin_email: str | None = None
    ip_address: str | None = None
    created_at: str


class AuditLogResponse(BaseModel):
    items: list[AuditLogItem]
    total: int


@router.get("/logs", response_model=AuditLogResponse)
async def list_audit_logs(
    action: str = Query(""),
    target_type: str = Query(""),
    admin_email: str = Query(""),
    start_date: str = Query(""),
    end_date: str = Query(""),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs with filtering."""
    query = select(AuditLog, User).join(User, AuditLog.admin_id == User.id)

    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if target_type:
        query = query.where(AuditLog.target_type == target_type)
    if admin_email:
        query = query.where(User.email.ilike(f"%{admin_email}%"))
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)

    total = await db.scalar(select(func.count(AuditLog.id)).select_from(query.subquery()))

    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)

    items = [
        AuditLogItem(
            id=str(a.id),
            action=a.action,
            target_type=a.target_type,
            target_id=a.target_id,
            details=a.details,
            admin_email=u.email,
            ip_address=a.ip_address,
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a, u in result.all()
    ]

    return AuditLogResponse(items=items, total=total or 0)


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


class FeatureFlagItem(BaseModel):
    id: str
    key: str
    name: str
    description: str | None = None
    default_enabled: bool
    requires_plan: str | None = None


class FeatureFlagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    default_enabled: bool | None = None
    requires_plan: str | None = None


class UserOverrideItem(BaseModel):
    user_id: str
    feature_key: str
    enabled: bool


@router.get("/features", response_model=list[FeatureFlagItem])
async def list_feature_flags(
    admin_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """List all feature flags."""
    result = await db.execute(select(FeatureFlag).order_by(FeatureFlag.key))
    return [
        FeatureFlagItem(
            id=str(f.id), key=f.key, name=f.name,
            description=f.description, default_enabled=f.default_enabled,
            requires_plan=f.requires_plan,
        )
        for f in result.scalars().all()
    ]


class CreateFeatureFlagRequest(BaseModel):
    key: str
    name: str
    description: str | None = None
    default_enabled: bool = True
    requires_plan: str | None = None


@router.post("/features", response_model=FeatureFlagItem)
async def create_feature_flag(
    body: CreateFeatureFlagRequest,
    admin_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Create a new feature flag."""
    existing = await db.execute(select(FeatureFlag).where(FeatureFlag.key == body.key))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Feature flag key already exists")

    flag = FeatureFlag(
        key=body.key, name=body.name, description=body.description,
        default_enabled=body.default_enabled, requires_plan=body.requires_plan,
    )
    db.add(flag)
    await db.flush()
    return FeatureFlagItem(
        id=str(flag.id), key=flag.key, name=flag.name,
        description=flag.description, default_enabled=flag.default_enabled,
        requires_plan=flag.requires_plan,
    )


@router.patch("/features/{feature_id}", response_model=FeatureFlagItem)
async def update_feature_flag(
    feature_id: str,
    body: FeatureFlagUpdate,
    admin_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Update a feature flag."""
    try:
        fid = uuid.UUID(feature_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    result = await db.execute(select(FeatureFlag).where(FeatureFlag.id == fid))
    flag = result.scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=404, detail="Feature flag not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(flag, field, value)
    await db.flush()

    return FeatureFlagItem(
        id=str(flag.id), key=flag.key, name=flag.name,
        description=flag.description, default_enabled=flag.default_enabled,
        requires_plan=flag.requires_plan,
    )


@router.get("/features/users/{user_id}", response_model=list[UserOverrideItem])
async def list_user_overrides(
    user_id: str,
    admin_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """List feature overrides for a specific user."""
    result = await db.execute(
        select(UserFeatureOverride).where(UserFeatureOverride.user_id == uuid.UUID(user_id))
    )
    return [
        UserOverrideItem(
            user_id=str(o.user_id), feature_key=o.feature_key, enabled=o.enabled,
        )
        for o in result.scalars().all()
    ]


@router.post("/features/users/{user_id}/override", response_model=UserOverrideItem)
async def set_user_override(
    user_id: str,
    body: UserOverrideItem,
    admin_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable a feature for a specific user."""
    result = await db.execute(
        select(UserFeatureOverride)
        .where(UserFeatureOverride.user_id == uuid.UUID(user_id))
        .where(UserFeatureOverride.feature_key == body.feature_key)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.enabled = body.enabled
        await db.flush()
        return UserOverrideItem(
            user_id=str(existing.user_id), feature_key=existing.feature_key,
            enabled=existing.enabled,
        )
    else:
        override = UserFeatureOverride(
            user_id=uuid.UUID(user_id), feature_key=body.feature_key, enabled=body.enabled,
        )
        db.add(override)
        await db.flush()
        return UserOverrideItem(
            user_id=str(override.user_id), feature_key=override.feature_key,
            enabled=override.enabled,
        )
