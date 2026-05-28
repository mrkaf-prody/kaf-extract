"""POST /api/v1/extract/schedule — Recurring extraction schedules.

Supports cron-based scheduling of extraction jobs.
Jobs are executed via the background scheduler loop.
"""

import json
from datetime import UTC, datetime
from typing import Any

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.auth import get_current_user
from src.models.sql_models import ScheduledExtraction
from src.services.scheduler import compute_next_run

router = APIRouter(tags=["schedule"])


# ── Request / Response Schemas ────────────────────────────────────

class ScheduleField(BaseModel):
    """A single field in the extraction schema."""
    name: str
    selector: str = ""
    type: str = "text"
    attribute: str | None = None
    instruction: str | None = None


class CreateScheduleRequest(BaseModel):
    """Request to create a recurring extraction schedule."""
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable name")
    cron_expression: str = Field(
        ..., min_length=1, max_length=100,
        description="Standard cron expression. Examples: '0 */6 * * *' (every 6h), '0 9 * * 1-5' (weekdays 9am)",
    )
    url: str = Field(..., description="Target URL to extract")
    fields: list[ScheduleField] = Field(..., min_length=1, description="Fields to extract")
    webhook_url: str | None = Field(None, description="Webhook to POST results to")
    email_on_complete: str | None = Field(None, description="Email notification address")


class ScheduleResponse(BaseModel):
    """Response for a scheduled extraction."""
    id: str
    name: str
    cron_expression: str
    url: str
    fields: list[dict[str, Any]]
    webhook_url: str | None
    email_on_complete: str | None
    status: str
    next_run_at: str | None
    last_run_at: str | None
    last_job_id: str | None
    total_runs: int
    error_runs: int
    created_at: str

    @classmethod
    def from_orm(cls, schedule: ScheduledExtraction) -> "ScheduleResponse":
        return cls(
            id=str(schedule.id),
            name=schedule.name,
            cron_expression=schedule.cron_expression,
            url=schedule.url,
            fields=json.loads(schedule.schema_json),
            webhook_url=schedule.webhook_url,
            email_on_complete=schedule.email_on_complete,
            status=schedule.status,
            next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
            last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
            last_job_id=schedule.last_job_id,
            total_runs=schedule.total_runs or 0,
            error_runs=schedule.error_runs or 0,
            created_at=schedule.created_at.isoformat() if schedule.created_at else "",
        )


class ScheduleListResponse(BaseModel):
    """List of scheduled extractions."""
    schedules: list[ScheduleResponse]
    total: int


# ── Helpers ────────────────────────────────────────────────────────

def _validate_cron(expression: str) -> bool:
    """Validate a cron expression. Raises ValueError if invalid."""
    try:
        croniter(expression, datetime.now(UTC))
        return True
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid cron expression: {e}",
        )


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("/extract/schedule", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: CreateScheduleRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a recurring extraction schedule.

    The extraction will run automatically according to the cron expression.
    Results are delivered via webhook_url if provided.

    Examples of cron expressions:
    - `0 */6 * * *` — Every 6 hours
    - `0 9 * * 1-5` — Weekdays at 9am UTC
    - `0 0 1 * *` — First day of every month at midnight
    - `*/30 * * * *` — Every 30 minutes
    """
    # Validate cron
    _validate_cron(body.cron_expression)

    # Serialize fields to JSON
    schema_json = json.dumps([f.model_dump() for f in body.fields])

    # Compute next run time
    now = datetime.now(UTC)
    next_run = compute_next_run(body.cron_expression, now)

    # Create schedule
    import uuid
    schedule = ScheduledExtraction(
        id=uuid.uuid4(),
        user_id=current_user["user_id"],
        name=body.name,
        cron_expression=body.cron_expression,
        url=body.url,
        schema_json=schema_json,
        webhook_url=body.webhook_url,
        email_on_complete=body.email_on_complete,
        status="active",
        next_run_at=next_run,
    )
    db.add(schedule)
    await db.flush()

    return ScheduleResponse.from_orm(schedule)


@router.get("/extract/schedules", response_model=ScheduleListResponse)
async def list_schedules(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all scheduled extractions for the current user."""
    result = await db.execute(
        select(ScheduledExtraction)
        .where(ScheduledExtraction.user_id == current_user["user_id"])
        .order_by(ScheduledExtraction.created_at.desc())
    )
    schedules = result.scalars().all()

    return ScheduleListResponse(
        schedules=[ScheduleResponse.from_orm(s) for s in schedules],
        total=len(schedules),
    )


@router.get("/extract/schedule/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single scheduled extraction by ID."""
    import uuid as _uuid
    result = await db.execute(
        select(ScheduledExtraction).where(
            ScheduledExtraction.id == _uuid.UUID(schedule_id),
            ScheduledExtraction.user_id == current_user["user_id"],
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return ScheduleResponse.from_orm(schedule)


@router.delete("/extract/schedule/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scheduled extraction."""
    import uuid as _uuid
    result = await db.execute(
        select(ScheduledExtraction).where(
            ScheduledExtraction.id == _uuid.UUID(schedule_id),
            ScheduledExtraction.user_id == current_user["user_id"],
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await db.delete(schedule)
    await db.flush()


@router.post("/extract/schedule/{schedule_id}/pause", response_model=ScheduleResponse)
async def pause_schedule(
    schedule_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pause a scheduled extraction."""
    import uuid as _uuid
    result = await db.execute(
        select(ScheduledExtraction).where(
            ScheduledExtraction.id == _uuid.UUID(schedule_id),
            ScheduledExtraction.user_id == current_user["user_id"],
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule.status = "paused"
    schedule.next_run_at = None
    await db.flush()

    return ScheduleResponse.from_orm(schedule)


@router.post("/extract/schedule/{schedule_id}/resume", response_model=ScheduleResponse)
async def resume_schedule(
    schedule_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused scheduled extraction."""
    import uuid as _uuid
    result = await db.execute(
        select(ScheduledExtraction).where(
            ScheduledExtraction.id == _uuid.UUID(schedule_id),
            ScheduledExtraction.user_id == current_user["user_id"],
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if schedule.status != "paused":
        raise HTTPException(status_code=400, detail="Schedule is not paused")

    schedule.status = "active"
    schedule.next_run_at = compute_next_run(schedule.cron_expression)
    await db.flush()

    return ScheduleResponse.from_orm(schedule)
