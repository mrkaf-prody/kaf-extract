"""Usage alert service — email notification at 80%/90%/100% thresholds."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import async_session_factory
from src.models.sql_models import UsageAlert

RESEND_API = "https://api.resend.com/emails"
FROM_EMAIL = "hermizy@kafcenter.com"
TO_EMAIL = "kamal2jo@gmail.com"

_alert_messages = {
    80: "⚠️ 80% usage: {current}/{limit} extractions this month. Consider upgrading.",
    90: "🔴 90% usage: {current}/{limit} extractions this month. Upgrade soon to avoid interruption.",
    100: "🚨 LIMIT REACHED: {current}/{limit} extractions this month.",
}


async def _send_email(subject: str, body: str, resend_key: str) -> bool:
    """Send alert email via Resend API."""
    try:
        async with httpx.AsyncClient(timeout=10) as cl:
            r = await cl.post(
                RESEND_API,
                headers={"Authorization": f"Bearer {resend_key}"},
                json={
                    "from": FROM_EMAIL,
                    "to": [TO_EMAIL],
                    "subject": f"[Kaf Extract] {subject}",
                    "text": body,
                },
            )
        return r.status_code == 200
    except Exception:
        return False


async def increment_usage(
    user_id: UUID, resend_key: str | None = None
) -> dict:
    """Increment usage counter and check thresholds. Returns alert status.

    Called after every successful extraction.
    """
    import os

    now = datetime.now(UTC)
    next_reset = _compute_next_reset(now)

    async with async_session_factory() as db:
        result = await db.execute(
            select(UsageAlert).where(UsageAlert.user_id == user_id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            alert = UsageAlert(
                user_id=user_id,
                monthly_limit=1000,
                reset_date=next_reset,
                current_usage=0,
            )
            db.add(alert)
            await db.flush()

        # New month reset
        if now >= alert.reset_date:
            alert.current_usage = 0
            alert.alert_80_sent = False
            alert.alert_90_sent = False
            alert.alert_100_sent = False
            alert.reset_date = next_reset

        # Increment
        alert.current_usage += 1
        pct = int((alert.current_usage / alert.monthly_limit) * 100)
        alerts_fired = []
        key = resend_key or os.getenv("RESEND_API_KEY", "")

        if pct >= 80 and not alert.alert_80_sent:
            alert.alert_80_sent = True
            if key:
                await _send_email(
                    "80% Usage Alert",
                    _alert_messages[80].format(current=alert.current_usage, limit=alert.monthly_limit),
                    key,
                )
            alerts_fired.append("80%")

        if pct >= 90 and not alert.alert_90_sent:
            alert.alert_90_sent = True
            if key:
                await _send_email(
                    "90% Usage Alert",
                    _alert_messages[90].format(current=alert.current_usage, limit=alert.monthly_limit),
                    key,
                )
            alerts_fired.append("90%")

        hard_capped = False
        if pct >= 100:
            if not alert.alert_100_sent:
                alert.alert_100_sent = True
                if key:
                    await _send_email(
                        "Limit Reached",
                        _alert_messages[100].format(current=alert.current_usage, limit=alert.monthly_limit),
                        key,
                    )
                alerts_fired.append("100%")
            if alert.hard_cap and alert.current_usage >= alert.hard_cap:
                hard_capped = True

        await db.flush()

        return {
            "current_usage": alert.current_usage,
            "monthly_limit": alert.monthly_limit,
            "hard_cap": alert.hard_cap,
            "hard_capped": hard_capped,
            "percent": min(pct, 100),
            "alerts_fired": alerts_fired,
        }


def _compute_next_reset(now: datetime) -> datetime:
    """First day of next month at midnight UTC."""
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, tzinfo=UTC)
    return datetime(now.year, now.month + 1, 1, tzinfo=UTC)
