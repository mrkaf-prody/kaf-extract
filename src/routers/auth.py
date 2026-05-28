"""Auth router — user registration, login, token refresh."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db
from src.middleware.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from src.models.sql_models import RefreshToken, User

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Request / Response Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    status: str
    created_at: str


class MessageResponse(BaseModel):
    message: str


# --- Helpers ---

def _hash_password(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        import bcrypt
        return bcrypt.checkpw(plain.encode(), hashed.encode())


async def _store_refresh_token(
    db: AsyncSession, user_id: uuid.UUID, raw_token: str
) -> None:
    """Hash and store a refresh token in the database."""
    try:
        token_hash = pwd_context.hash(raw_token)
    except Exception:
        import bcrypt
        token_hash = bcrypt.hashpw(raw_token.encode(), bcrypt.gensalt()).decode()
    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    rt = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(rt)
    await db.flush()


async def _validate_and_consume_refresh_token(
    db: AsyncSession, raw_token: str
) -> uuid.UUID:
    """Validate a refresh token (JWT + DB lookup), consume it, return user_id."""
    # Decode JWT
    try:
        payload = decode_token(raw_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not a refresh token",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    user_id = uuid.UUID(user_id_str)

    # Look up in DB: find a matching refresh token hash
    from src.models.sql_models import RefreshToken as RT

    all_tokens = await db.execute(
        select(RT).where(RT.user_id == user_id)
    )
    found = False
    for rt in all_tokens.scalars():
        if pwd_context.verify(raw_token, rt.token_hash):
            # Valid — consume (delete) this token
            await db.delete(rt)
            found = True
            break

    if not found:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found or already used",
        )

    return user_id


# --- Endpoints ---

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account. Returns JWT access + refresh tokens."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        password_hash=_hash_password(body.password),
        name=body.name,
        role="user",
        status="active",
    )
    db.add(user)
    await db.flush()

    # Auto-start trial for new users
    try:
        from src.services.trials import start_trial
        await start_trial(db, user.id)
    except Exception:
        pass  # Non-fatal — user can still use the service

    # Generate tokens
    access_token = create_access_token(str(user.id), user.email, user.role)
    refresh_token = create_refresh_token(str(user.id))
    await _store_refresh_token(db, user.id, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email + password. Returns JWT tokens."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not _verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended",
        )

    access_token = create_access_token(str(user.id), user.email, user.role)
    refresh_token = create_refresh_token(str(user.id))
    await _store_refresh_token(db, user.id, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access + refresh token pair."""
    user_id = await _validate_and_consume_refresh_token(db, body.refresh_token)

    # Get user info
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = create_access_token(str(user.id), user.email, user.role)
    new_refresh_token = create_refresh_token(str(user.id))
    await _store_refresh_token(db, user.id, new_refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return the currently authenticated user's profile."""
    result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        status=user.status,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )
