"""Integration endpoints — Slack, webhooks, exports.

POST /api/v1/integrations/slack/test — Test a Slack webhook
GET /api/v1/extract/history — Recent extraction history for export
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.auth import get_current_user
from src.models.sql_models import ScheduledExtraction

router = APIRouter(tags=["integrations"])


# ── Schemas ────────────────────────────────────────────────────────

class SlackTestRequest(BaseModel):
    webhook_url: str = Field(..., description="Slack incoming webhook URL")


class SlackTestResponse(BaseModel):
    success: bool
    message: str


class ExtractionHistoryItem(BaseModel):
    """A single extraction history entry (from scheduled_extractions log)."""
    id: str
    name: str | None
    url: str
    status: str
    last_run_at: str | None
    last_job_id: str | None
    total_runs: int
    error_runs: int


class ExtractionHistoryResponse(BaseModel):
    history: list[ExtractionHistoryItem]
    total: int


# ── Slack Test ─────────────────────────────────────────────────────

@router.post("/integrations/slack/test", response_model=SlackTestResponse)
async def test_slack_webhook(
    body: SlackTestRequest,
    current_user: dict = Depends(get_current_user),
):
    """Test a Slack webhook URL by sending a sample notification.

    Sends a formatted test message to confirm the webhook works.
    """
    from src.services.slack import send_slack_notification

    ok = await send_slack_notification(
        webhook_url=body.webhook_url,
        extraction_url="https://example.com (test)",
        status="success",
        data={"test": True, "message": "Your Kaf Extract Slack integration is working! 🎉"},
        job_id="test-123",
    )

    if ok:
        return SlackTestResponse(
            success=True,
            message="Test notification sent! Check your Slack channel.",
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Failed to send Slack notification. Check your webhook URL.",
        )


# ── Extraction History ─────────────────────────────────────────────

@router.get("/extract/history", response_model=ExtractionHistoryResponse)
async def extraction_history(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
):
    """Get recent extraction history from scheduled extractions.

    Shows all scheduled extraction runs with their status, timing, and job IDs.
    Use this to export/download past extraction results.
    """
    result = await db.execute(
        select(ScheduledExtraction)
        .where(
            ScheduledExtraction.user_id == current_user["user_id"],
            ScheduledExtraction.last_run_at.isnot(None),
        )
        .order_by(ScheduledExtraction.last_run_at.desc())
        .limit(limit)
    )
    schedules = result.scalars().all()

    history = [
        ExtractionHistoryItem(
            id=str(s.id),
            name=s.name,
            url=s.url,
            status="success" if s.error_runs == 0 or s.last_job_id else "mixed",
            last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
            last_job_id=s.last_job_id,
            total_runs=s.total_runs or 0,
            error_runs=s.error_runs or 0,
        )
        for s in schedules
    ]

    # Also count total runs
    count_result = await db.execute(
        select(func.count(ScheduledExtraction.id)).where(
            ScheduledExtraction.user_id == current_user["user_id"],
            ScheduledExtraction.last_run_at.isnot(None),
        )
    )
    total = count_result.scalar() or 0

    return ExtractionHistoryResponse(history=history, total=total)
