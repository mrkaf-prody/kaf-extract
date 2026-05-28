"""Background scheduler for recurring extractions.

Runs a polling loop that checks for due scheduled_extractions every 30 seconds.
When a schedule is due, enqueues the extraction via arq and computes the next run time.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from croniter import croniter
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import async_session_factory
from src.models.sql_models import ScheduledExtraction

logger = logging.getLogger(__name__)

# How often to check for due schedules (seconds)
POLL_INTERVAL = 30

# Global flag to stop the loop
_scheduler_task: asyncio.Task | None = None


def compute_next_run(cron_expression: str, base_time: datetime | None = None) -> datetime:
    """Compute the next run time from a cron expression.

    Args:
        cron_expression: Standard cron expression (5-field).
        base_time: Reference time. Defaults to now.

    Returns:
        UTC datetime of the next scheduled run.
    """
    base = base_time or datetime.now(UTC)
    cron = croniter(cron_expression, base)
    return cron.get_next(datetime)


async def _process_due_schedules(db: AsyncSession) -> int:
    """Find all due schedules and enqueue their extractions.

    Returns the number of jobs enqueued.
    """
    now = datetime.now(UTC)

    # Find active schedules where next_run_at <= now
    result = await db.execute(
        select(ScheduledExtraction).where(
            ScheduledExtraction.status == "active",
            ScheduledExtraction.next_run_at <= now,
        )
    )
    due_schedules = result.scalars().all()

    if not due_schedules:
        return 0

    enqueued = 0
    for schedule in due_schedules:
        try:
            # Parse the stored schema
            fields = json.loads(schedule.schema_json)

            # Enqueue via arq
            from src.services.queue import enqueue_extraction

            job_id = await enqueue_extraction(
                url=schedule.url,
                fields=fields,
                api_key_id=str(schedule.user_id),
                webhook_url=schedule.webhook_url,
            )

            # Compute next run time
            next_run = compute_next_run(schedule.cron_expression, now)

            # Update schedule record
            await db.execute(
                update(ScheduledExtraction)
                .where(ScheduledExtraction.id == schedule.id)
                .values(
                    last_run_at=now,
                    last_job_id=job_id,
                    next_run_at=next_run,
                    total_runs=ScheduledExtraction.total_runs + 1,
                    updated_at=now,
                )
            )

            logger.info(
                "Schedule %s (%s) executed: job_id=%s, next_run=%s",
                schedule.name, schedule.id, job_id, next_run.isoformat()
            )
            enqueued += 1

        except Exception as exc:
            logger.error(
                "Schedule %s (%s) failed: %s",
                schedule.name, schedule.id, exc,
            )
            # Increment error count
            await db.execute(
                update(ScheduledExtraction)
                .where(ScheduledExtraction.id == schedule.id)
                .values(
                    last_run_at=now,
                    error_runs=ScheduledExtraction.error_runs + 1,
                    updated_at=now,
                )
            )

    if enqueued:
        await db.commit()
        logger.info("Processed %d due schedules (%d enqueued)", len(due_schedules), enqueued)

    return enqueued


async def scheduler_loop() -> None:
    """Main scheduler loop — runs forever, checks for due schedules every POLL_INTERVAL seconds.

    Called from FastAPI lifespan. Re-raises on first failure to allow restart.
    """
    logger.info("Scheduler loop started (poll interval: %ds)", POLL_INTERVAL)

    consecutive_failures = 0

    while True:
        try:
            async with async_session_factory() as db:
                await _process_due_schedules(db)
            consecutive_failures = 0

        except Exception as exc:
            consecutive_failures += 1
            logger.error(
                "Scheduler loop error (failure #%d): %s",
                consecutive_failures, exc,
            )
            if consecutive_failures >= 5:
                logger.critical("Scheduler loop: too many consecutive failures, stopping")
                raise

        await asyncio.sleep(POLL_INTERVAL)


def start_scheduler() -> asyncio.Task:
    """Start the scheduler as a background asyncio task.

    Returns the task handle for cancellation during shutdown.
    """
    global _scheduler_task
    _scheduler_task = asyncio.create_task(scheduler_loop())
    return _scheduler_task


async def stop_scheduler() -> None:
    """Cancel the scheduler background task."""
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
        logger.info("Scheduler loop stopped")
