"""Voucher router — admin CRUD + user redemption."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.auth import admin_required, get_current_user
from src.services.vouchers import voucher_service

router = APIRouter(prefix="/api/v1", tags=["vouchers"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    plan: str = "pro"
    quantity: int = Field(default=5, ge=1, le=500)
    duration_days: int = Field(default=30, ge=1, le=3650)
    extraction_credits: int = Field(default=0, ge=0)
    max_uses: int = Field(default=1, ge=1)
    expiry_date: str | None = None  # ISO date string


class GenerateResponse(BaseModel):
    codes: list[str]
    plan: str
    quantity: int


class VoucherResponse(BaseModel):
    id: str
    code: str
    plan: str
    duration_days: int
    extraction_credits: int
    max_uses: int
    used_count: int
    status: str
    created_by: str | None = None
    created_at: str
    expires_at: str


class VoucherListResponse(BaseModel):
    vouchers: list[VoucherResponse]
    total: int
    offset: int
    limit: int


class RedeemRequest(BaseModel):
    code: str


class RedeemResponse(BaseModel):
    subscription_id: str
    plan: str
    duration_days: int
    period_end: str
    extraction_credits: int


class RedemptionHistoryItem(BaseModel):
    id: str
    voucher_code: str
    voucher_plan: str
    redeemed_at: str


class RedemptionHistoryResponse(BaseModel):
    redemptions: list[RedemptionHistoryItem]
    total: int
    offset: int
    limit: int


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _voucher_to_response(v: Any) -> VoucherResponse:
    return VoucherResponse(
        id=str(v.id),
        code=v.code,
        plan=v.plan,
        duration_days=v.duration_days,
        extraction_credits=v.extraction_credits,
        max_uses=v.max_uses,
        used_count=v.used_count,
        status=v.status,
        created_by=str(v.created_by) if v.created_by else None,
        created_at=v.created_at.isoformat() if v.created_at else "",
        expires_at=v.expires_at.isoformat() if v.expires_at else "",
    )


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/admin/vouchers/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_vouchers(
    body: GenerateRequest,
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Generate a batch of voucher codes (admin only)."""
    expiry = None
    if body.expiry_date:
        try:
            expiry = datetime.fromisoformat(body.expiry_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid expiry_date format. Use ISO format (e.g. 2026-12-31)",
            )

    try:
        vouchers = await voucher_service.generate_batch(
            db,
            plan=body.plan,
            quantity=body.quantity,
            duration_days=body.duration_days,
            extraction_credits=body.extraction_credits,
            max_uses=body.max_uses,
            expiry_date=expiry,
            prefix=body.prefix,
            created_by=admin["user_id"],
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    codes = [v.code for v in vouchers]
    return GenerateResponse(
        codes=codes,
        plan=body.plan,
        quantity=len(codes),
    )


@router.get("/admin/vouchers", response_model=VoucherListResponse)
async def list_vouchers(
    status_filter: str | None = Query(default=None, alias="status"),
    plan: str | None = Query(default=None),
    search: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """List vouchers with optional filters (admin only)."""
    vouchers, total = await voucher_service.list_vouchers(
        db,
        status=status_filter,
        plan=plan,
        search=search,
        offset=offset,
        limit=limit,
    )
    return VoucherListResponse(
        vouchers=[_voucher_to_response(v) for v in vouchers],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/admin/vouchers/export")
async def export_vouchers_csv(
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Export unused vouchers as CSV (admin only)."""
    csv_content = await voucher_service.export_unused_csv(db)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=vouchers-export.csv"
        },
    )


@router.delete("/admin/vouchers/{voucher_id}")
async def invalidate_voucher(
    voucher_id: uuid.UUID,
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Invalidate (revoke) a voucher (admin only)."""
    try:
        voucher = await voucher_service.invalidate_voucher(db, voucher_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return _voucher_to_response(voucher)


# ---------------------------------------------------------------------------
# User-facing endpoints
# ---------------------------------------------------------------------------


@router.post("/vouchers/redeem", response_model=RedeemResponse)
async def redeem_voucher(
    body: RedeemRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Redeem a voucher code to activate a subscription."""
    ip = request.client.host if request.client else None
    try:
        result = await voucher_service.redeem_voucher(
            db,
            user_id=current_user["user_id"],
            code=body.code,
            ip_address=ip,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return RedeemResponse(**result)


@router.get("/vouchers/history", response_model=RedemptionHistoryResponse)
async def get_redemption_history(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's voucher redemption history."""
    redemptions, total = await voucher_service.get_redemption_history(
        db,
        user_id=current_user["user_id"],
        offset=offset,
        limit=limit,
    )

    items = []
    for r in redemptions:
        code = r.voucher.code if r.voucher else "unknown"
        plan = r.voucher.plan if r.voucher else "unknown"
        items.append(
            RedemptionHistoryItem(
                id=str(r.id),
                voucher_code=code,
                voucher_plan=plan,
                redeemed_at=r.redeemed_at.isoformat() if r.redeemed_at else "",
            )
        )

    return RedemptionHistoryResponse(
        redemptions=items,
        total=total,
        offset=offset,
        limit=limit,
    )
