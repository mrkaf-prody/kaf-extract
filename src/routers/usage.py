"""Usage alerts & quotas API endpoints.

GET  /api/v1/usage          — Get current usage stats
PUT  /api/v1/usage/limits   — Set monthly_limit / hard_cap
POST /api/v1/usage/reset    — Reset monthly counters (admin only)
"""

import os
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.auth import get_current_user
from src.models.sql_models import UsageAlert
from src.services.usage_alerts import increment_usage

router = APIRouter(tags=["usage"])


class UsageResponse(BaseModel):
    current_usage: int
    monthly_limit: int
    hard_cap: int | None
    percent: int
    reset_date: str
    alerts_sent: dict


class SetLimitsRequest(BaseModel):
    monthly_limit: int | None = Field(default=None, ge=100, le=100000)
    hard_cap: int | None = Field(default=None, ge=100, le=500000)


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current usage stats for the authenticated user."""
    import traceback, sys
    try:
        return await _get_usage_impl(current_user, db)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


async def _get_usage_impl(current_user, db):
    user_id = current_user["user_id"]

    result = await db.execute(
        select(UsageAlert).where(UsageAlert.user_id == user_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        return UsageResponse(
            current_usage=0,
            monthly_limit=1000,
            hard_cap=None,
            percent=0,
            reset_date=_next_reset_date(),
            alerts_sent={},
        )

    pct = min(int((alert.current_usage / alert.monthly_limit) * 100), 100)
    alerts = {}
    if alert.alert_80_sent:
        alerts["80"] = True
    if alert.alert_90_sent:
        alerts["90"] = True
    if alert.alert_100_sent:
        alerts["100"] = True

    return UsageResponse(
        current_usage=alert.current_usage,
        monthly_limit=alert.monthly_limit,
        hard_cap=alert.hard_cap,
        percent=pct,
        reset_date=alert.reset_date.isoformat(),
        alerts_sent=alerts,
    )


@router.put("/usage/limits", response_model=UsageResponse)
async def set_limits(
    body: SetLimitsRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set monthly usage limits and hard cap."""
    user_id = current_user["user_id"]

    result = await db.execute(
        select(UsageAlert).where(UsageAlert.user_id == user_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        alert = UsageAlert(
            user_id=user_id,
            monthly_limit=1000,
            reset_date=datetime.now(UTC).replace(day=1),
        )
        db.add(alert)

    if body.monthly_limit is not None:
        alert.monthly_limit = body.monthly_limit
    if body.hard_cap is not None:
        alert.hard_cap = body.hard_cap

    await db.flush()

    pct = min(int((alert.current_usage / alert.monthly_limit) * 100), 100)
    alerts = {}
    if alert.alert_80_sent:
        alerts["80"] = True
    if alert.alert_90_sent:
        alerts["90"] = True
    if alert.alert_100_sent:
        alerts["100"] = True

    return UsageResponse(
        current_usage=alert.current_usage,
        monthly_limit=alert.monthly_limit,
        hard_cap=alert.hard_cap,
        percent=pct,
        reset_date=alert.reset_date.isoformat(),
        alerts_sent=alerts,
    )


@router.post("/usage/track")
async def track_usage(
    current_user: dict = Depends(get_current_user),
):
    """Increment usage counter (called after successful extraction)."""
    user_id = current_user["user_id"]
    key = os.getenv("RESEND_API_KEY", "")
    result = await increment_usage(user_id, resend_key=key if key else None)
    return result


def _next_reset_date() -> str:
    """First day of next month."""
    now = datetime.now(UTC)
    if now.month == 12:
        nxt = now.replace(year=now.year + 1, month=1, day=1)
    else:
        nxt = now.replace(month=now.month + 1, day=1)
    return nxt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
