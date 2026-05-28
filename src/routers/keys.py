"""API Key management — admin CRUD + user listing.

Admin-only endpoints:
- POST   /api/v1/admin/keys       Create a new API key
- GET    /api/v1/admin/keys       List all API keys (filterable, paginated)
- DELETE /api/v1/admin/keys/{id}  Revoke an API key (soft delete)

User endpoint:
- GET    /api/v1/keys             Current user lists their own keys
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.auth import admin_required, get_current_user
from src.models.sql_models import ApiKey, User

router = APIRouter(tags=["keys"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CreateKeyRequest(BaseModel):
    """Request body for creating an API key."""

    label: str = Field(
        ..., min_length=1, max_length=255, description="Human-readable label for this key"
    )
    tier: str = Field(
        default="hobby",
        pattern="^(hobby|pro|enterprise)$",
        description="API key tier",
    )
    rate_limit: int = Field(
        default=100,
        ge=1,
        le=100000,
        description="Rate limit (requests per window)",
    )


class CreateKeyResponse(BaseModel):
    """Response after creating an API key — raw key returned ONLY once."""

    id: str
    label: str
    tier: str
    rate_limit: int
    api_key: str  # The raw key — shown only on creation
    message: str = "Store this key securely. It will not be shown again."


class ApiKeyItem(BaseModel):
    """A single API key in a list response."""

    id: str
    user_id: str
    user_email: str
    label: str
    tier: str
    rate_limit: int
    status: str
    last_used_at: str | None
    created_at: str


class KeyListResponse(BaseModel):
    """Paginated list of API keys."""

    keys: list[ApiKeyItem]
    total: int
    offset: int
    limit: int


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_api_key() -> str:
    """Generate a random API key with kaf_ prefix."""
    random_part = secrets.token_urlsafe(32)
    return f"kaf_{random_part}"


def _hash_api_key(raw_key: str) -> str:
    """Hash an API key using bcrypt."""
    return pwd_context.hash(raw_key)


def _model_to_item(api_key: ApiKey, user: User | None = None) -> ApiKeyItem:
    """Convert an ApiKey ORM model (and optional User) to a response item."""
    user_email = user.email if user else "unknown"
    return ApiKeyItem(
        id=str(api_key.id),
        user_id=str(api_key.user_id),
        user_email=user_email,
        label=api_key.label,
        tier=api_key.tier,
        rate_limit=api_key.rate_limit,
        status=api_key.status,
        last_used_at=api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        created_at=api_key.created_at.isoformat() if api_key.created_at else "",
    )


# ---------------------------------------------------------------------------
# Admin endpoints (require admin role)
# ---------------------------------------------------------------------------

@router.post(
    "/admin/keys",
    response_model=CreateKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_key(
    body: CreateKeyRequest,
    current_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key (admin only).

    The raw key is returned exactly once in this response.
    It is stored as a bcrypt hash in the database.
    """
    raw_key = _generate_api_key()
    key_hash = _hash_api_key(raw_key)

    # Verify the target user exists (current admin user)
    user_id = current_user["user_id"]
    result = await db.execute(select(User).where(User.id == user_id, User.status == "active"))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or inactive",
        )

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=user_id,
        key_hash=key_hash,
        label=body.label,
        tier=body.tier,
        rate_limit=body.rate_limit,
        status="active",
        created_at=datetime.now(UTC),
    )
    db.add(api_key)
    await db.flush()

    return CreateKeyResponse(
        id=str(api_key.id),
        label=api_key.label,
        tier=api_key.tier,
        rate_limit=api_key.rate_limit,
        api_key=raw_key,
    )


@router.get("/admin/keys", response_model=KeyListResponse)
async def list_keys(
    user_id: str | None = Query(None, description="Filter by user ID"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status (active, revoked)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    current_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys (admin only).

    Supports filtering by user_id and status, and pagination via offset/limit.
    """
    # Build base query
    query = select(ApiKey, User).join(User, ApiKey.user_id == User.id)
    count_query = select(func.count(ApiKey.id)).join(User, ApiKey.user_id == User.id)

    if user_id:
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user_id UUID format",
            )
        query = query.where(ApiKey.user_id == uid)
        count_query = count_query.where(ApiKey.user_id == uid)

    if status_filter:
        if status_filter not in ("active", "revoked"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status must be 'active' or 'revoked'",
            )
        query = query.where(ApiKey.status == status_filter)
        count_query = count_query.where(ApiKey.status == status_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.order_by(ApiKey.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    keys = [_model_to_item(ak, u) for ak, u in rows]

    return KeyListResponse(
        keys=keys,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.delete("/admin/keys/{key_id}", response_model=MessageResponse)
async def revoke_key(
    key_id: str,
    current_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key by ID (admin only, soft delete).

    Sets the key status to 'revoked'. The key hash remains in the database.
    """
    try:
        kid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key_id UUID format",
        )

    result = await db.execute(select(ApiKey).where(ApiKey.id == kid))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if api_key.status == "revoked":
        return MessageResponse(message="API key was already revoked")

    api_key.status = "revoked"
    await db.flush()

    return MessageResponse(message=f"API key '{api_key.label}' has been revoked")


# ---------------------------------------------------------------------------
# User endpoint (non-admin, lists own keys)
# ---------------------------------------------------------------------------

@router.get("/keys", response_model=list[ApiKeyItem])
async def list_my_keys(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List API keys belonging to the currently authenticated user."""
    user_id = current_user["user_id"]

    result = await db.execute(
        select(ApiKey, User)
        .join(User, ApiKey.user_id == User.id)
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
    )
    rows = result.all()

    return [_model_to_item(ak, u) for ak, u in rows]


# ---------------------------------------------------------------------------
# Router suffix for API version prefix
# ---------------------------------------------------------------------------

# These routes are mounted at /api/v1 in main.py, so the paths above are
# relative to that prefix:
#   POST   /api/v1/admin/keys
#   GET    /api/v1/admin/keys
#   DELETE /api/v1/admin/keys/{key_id}
#   GET    /api/v1/keys
