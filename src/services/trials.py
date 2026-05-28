"""Trial system — 7-day, 100-extraction trial for new users.

Automatically starts on registration.  Sends email reminders on day 3 and
day 6 via Resend.  Admins can extend trials.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.sql_models import Trial, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trial lifecycle
# ---------------------------------------------------------------------------


async def start_trial(db: AsyncSession, user_id: uuid.UUID) -> Trial:
    """Start a 7-day trial for a newly registered user.

    Call this immediately after user registration.
    """
    # Check if user already has a trial
    existing = await db.execute(
        select(Trial).where(Trial.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        logger.warning("User %s already has a trial — skipping", user_id)
        raise ValueError("User already has a trial")

    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.trial_duration_days)

    trial = Trial(
        id=uuid.uuid4(),
        user_id=user_id,
        status="active",
        extractions_total=settings.trial_extraction_limit,
        extractions_used=0,
        started_at=now,
        expires_at=expires_at,
    )
    db.add(trial)
    await db.flush()

    logger.info(
        "Trial started for user %s — expires %s",
        user_id,
        expires_at.isoformat(),
    )

    return trial


async def get_trial(db: AsyncSession, user_id: uuid.UUID) -> Trial | None:
    """Get the current trial for a user, if any."""
    result = await db.execute(
        select(Trial).where(Trial.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def check_trial(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Check if a user has an active trial with remaining extractions.

    Returns True if the user can use the service under trial.
    """
    trial = await get_trial(db, user_id)
    if trial is None:
        return False

    now = datetime.now(UTC)

    # Check if trial has expired
    if now > trial.expires_at and trial.status == "active":
        trial.status = "expired"
        await db.flush()
        logger.info("Trial expired for user %s", user_id)
        return False

    if trial.status != "active":
        return False

    # Check extractions remaining
    if trial.extractions_remaining <= 0:
        return False

    return True


async def consume_extraction(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Consume one extraction from the user's trial.

    Returns True if the extraction was consumed successfully,
    False if trial is not active or has no remaining extractions.
    """
    if not await check_trial(db, user_id):
        return False

    trial = await get_trial(db, user_id)
    if trial is None or trial.extractions_remaining <= 0:
        return False

    trial.extractions_used += 1
    await db.flush()

    return True


# ---------------------------------------------------------------------------
# Trial extension (admin)
# ---------------------------------------------------------------------------


async def extend_trial(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    extra_days: int = 7,
    extra_extractions: int = 100,
    admin_id: uuid.UUID | None = None,
) -> Trial | None:
    """Extend a user's trial. Called by admin.

    Resets status to 'extended' and adds days + extractions.
    """
    trial = await get_trial(db, user_id)
    if not trial:
        logger.warning("No trial found for user %s to extend", user_id)
        return None

    trial.status = "extended"
    trial.extractions_total += extra_extractions
    trial.expires_at = max(
        trial.expires_at, datetime.now(UTC)
    ) + timedelta(days=extra_days)
    trial.extended_by_id = admin_id
    trial.extended_at = datetime.now(UTC)

    await db.flush()

    logger.info(
        "Trial extended for user %s by admin %s — new expiry %s, "
        "total extractions %d",
        user_id,
        admin_id,
        trial.expires_at.isoformat(),
        trial.extractions_total,
    )

    return trial


# ---------------------------------------------------------------------------
# Daily cron: expire trials and send reminders
# ---------------------------------------------------------------------------


async def process_trial_expirations(db: AsyncSession) -> dict[str, int]:
    """Expire trials that have passed their end date.

    Intended to run once daily (e.g., via cron or scheduler).
    Returns counts of what was done.
    """
    now = datetime.now(UTC)

    result = await db.execute(
        select(Trial).where(
            Trial.status == "active",
            Trial.expires_at <= now,
        )
    )
    expired_trials = result.scalars().all()

    count = 0
    for trial in expired_trials:
        trial.status = "expired"
        count += 1

    await db.flush()

    if count:
        logger.info("Expired %d trials", count)

    return {"expired": count, "reminders_sent": 0}


async def send_trial_reminders(db: AsyncSession) -> dict[str, int]:
    """Send email reminders for trials on day 3 and day 6.

    Intended to run once daily.
    """
    now = datetime.now(UTC)

    # Find all active trials
    result = await db.execute(
        select(Trial).where(Trial.status.in_(["active", "extended"]))
    )
    trials = result.scalars().all()

    sent = 0

    for trial in trials:
        days_elapsed = (now - trial.started_at).days

        if days_elapsed >= 3 and not trial.reminder_sent_day3:
            # Day 3 reminder
            user_result = await db.execute(
                select(User).where(User.id == trial.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                await _send_reminder_email(
                    email=user.email,
                    name=user.name,
                    trial=trial,
                    days_left=(trial.expires_at - now).days,
                    reminder_type="day3",
                )
            trial.reminder_sent_day3 = True
            sent += 1

        if days_elapsed >= 6 and not trial.reminder_sent_day6:
            # Day 6 reminder (last day!)
            user_result = await db.execute(
                select(User).where(User.id == trial.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                await _send_reminder_email(
                    email=user.email,
                    name=user.name,
                    trial=trial,
                    days_left=(trial.expires_at - now).days,
                    reminder_type="day6",
                )
            trial.reminder_sent_day6 = True
            sent += 1

    await db.flush()

    if sent:
        logger.info("Sent %d trial reminder emails", sent)

    return {"expired": 0, "reminders_sent": sent}


# ---------------------------------------------------------------------------
# Email via Resend
# ---------------------------------------------------------------------------


async def _send_reminder_email(
    *,
    email: str,
    name: str | None,
    trial: Trial,
    days_left: int,
    reminder_type: str,
) -> None:
    """Send a trial reminder email via Resend API."""
    resend_key = settings.resend_api_key
    if not resend_key:
        logger.info(
            "RESEND_API_KEY not set — skipping trial reminder for %s", email
        )
        return

    display_name = name or email
    extractions_left = trial.extractions_remaining

    if reminder_type == "day3":
        subject = "Your Kaf Extract trial — you're halfway there!"
        body = (
            f"Hi {display_name},\n\n"
            f"You're 3 days into your 7-day Kaf Extract trial. "
            f"You have {extractions_left} extractions remaining.\n\n"
            f"Try our AI-powered extraction or batch processing!\n\n"
            f"Upgrade anytime: https://kafextract.com/pricing\n\n"
            f"— The Kaf Extract Team"
        )
    else:
        subject = "Last day of your Kaf Extract trial!"
        body = (
            f"Hi {display_name},\n\n"
            f"Your Kaf Extract trial ends tomorrow! "
            f"You have {extractions_left} extractions remaining.\n\n"
            f"Upgrade now to keep your extraction pipeline running:\n"
            f"https://kafextract.com/pricing\n\n"
            f"— The Kaf Extract Team"
        )

    try:
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.email_from,
                    "to": [email],
                    "subject": subject,
                    "text": body,
                },
            )

        if resp.status_code in (200, 201):
            logger.info("Sent %s reminder to %s", reminder_type, email)
        else:
            logger.warning(
                "Failed to send reminder to %s: %s %s",
                email,
                resp.status_code,
                resp.text[:200],
            )
    except Exception as exc:
        logger.error("Error sending reminder email to %s: %s", email, exc)


# ---------------------------------------------------------------------------
# Daily cron entrypoint
# ---------------------------------------------------------------------------


async def daily_trial_maintenance(db: AsyncSession) -> dict[str, int]:
    """Run all daily trial maintenance: expire + reminders.

    Call this once daily from a scheduler / cron job.
    """
    expire_result = await process_trial_expirations(db)
    reminder_result = await send_trial_reminders(db)

    return {
        "expired": expire_result["expired"],
        "reminders_sent": reminder_result["reminders_sent"],
    }
