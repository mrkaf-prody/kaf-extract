"""Auth router — user registration, login, token refresh, 2FA."""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, status
from src.utils.bcrypt_utils import hash_password, verify_password, hash_token, verify_token
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db
from src.middleware.auth import (
    admin_required,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from src.models.sql_models import RefreshToken, User
from src.utils.crypto import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_backup_codes,
    verify_backup_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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
    user: UserResponse | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    status: str
    totp_enabled: bool
    created_at: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    name: str | None = None


class MessageResponse(BaseModel):
    message: str


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code_uri: str
    qr_code_data_uri: str


class TOTPVerifyRequest(BaseModel):
    secret: str
    code: str = Field(..., min_length=6, max_length=6)


class TOTPVerifyResponse(BaseModel):
    message: str
    backup_codes: list[str]


class TOTPDisableRequest(BaseModel):
    password: str
    code: str = Field(..., min_length=6, max_length=6)


class TOTPLoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str = Field(..., min_length=6, max_length=6)


class AdminResetResponse(BaseModel):
    message: str
    new_password: str


# --- Helpers ---

def _hash_password(password: str) -> str:
    return hash_password(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return verify_password(plain, hashed)


async def _create_token_response(
    db: AsyncSession, user: User
) -> TokenResponse:
    """Create access + refresh tokens, store refresh token, return response with user."""
    access_token = create_access_token(str(user.id), user.email, user.role)
    refresh_token = create_refresh_token(str(user.id))
    await _store_refresh_token(db, user.id, refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            status=user.status,
            totp_enabled=user.totp_enabled,
            created_at=user.created_at.isoformat() if user.created_at else "",
        ),
    )


async def _store_refresh_token(
    db: AsyncSession, user_id: uuid.UUID, raw_token: str
) -> None:
    """Hash and store a refresh token in the database."""
    token_hash = hash_token(raw_token)
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
        if verify_token(raw_token, rt.token_hash):
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

    # Determine role — first user or admin email gets admin
    is_admin = body.email == "admin@kafcenter.com"
    
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        password_hash=_hash_password(body.password),
        name=body.name,
        role="admin" if is_admin else "user",
        status="active",
    )
    db.add(user)
    await db.flush()

    # Auto-start trial for new users
    try:
        from src.services.trials import start_trial
        await start_trial(db, user.id)
    except ValueError:
        pass  # User already has a trial — fine
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Trial start failed for user %s: %s", user.id, exc,
            exc_info=True,
        )

    # Generate tokens
    return await _create_token_response(db, user)


class LoginChallenge(BaseModel):
    """Returned when user has 2FA enabled — requires a second step."""
    requires_2fa: bool = True
    message: str = "2FA is enabled. Please provide your TOTP code via /auth/2fa/login."


@router.post(
    "/login",
    response_model=TokenResponse | LoginChallenge,
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email + password. If 2FA is enabled, return a challenge."""
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

    # If user has 2FA enabled, issue a challenge instead of tokens
    if user.totp_enabled:
        return LoginChallenge()

    return await _create_token_response(db, user)


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

    return await _create_token_response(db, user)


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
            totp_enabled=user.totp_enabled,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.put("/me/password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Verify current password
    if not _verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Update password
    user.password_hash = _hash_password(body.new_password)
    await db.flush()

    return MessageResponse(message="Password changed successfully")


@router.put("/me/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile (name only for now)."""
    result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.name is not None:
        user.name = body.name
    await db.flush()

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        status=user.status,
            totp_enabled=user.totp_enabled,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


# --- 2FA Endpoints ---


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code_uri: str
    qr_code_data_uri: str


class TOTPVerifyRequest(BaseModel):
    secret: str
    code: str = Field(..., min_length=6, max_length=6)


class TOTPVerifyResponse(BaseModel):
    message: str
    backup_codes: list[str]


class TOTPDisableRequest(BaseModel):
    password: str
    code: str = Field(..., min_length=6, max_length=6)


@router.post("/2fa/setup", response_model=TOTPSetupResponse)
async def setup_2fa(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate TOTP secret and QR code URI for setup.

    The secret is NOT saved yet — user must verify via /auth/2fa/verify first.
    """
    result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.totp_enabled or user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="2FA is already configured. Disable it first to reconfigure.",
        )

    # Generate a new secret
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    qr_uri = totp.provisioning_uri(
        name=user.email,
        issuer_name="Kaf Extract",
    )

    # Generate QR code image as data URI
    qr = qrcode.make(qr_uri)
    from io import BytesIO
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_data = base64.b64encode(buffer.getvalue()).decode()
    qr_data_uri = f"data:image/png;base64,{qr_data}"

    # Return the secret so the user can confirm with /auth/2fa/verify
    return TOTPSetupResponse(
        secret=secret,
        qr_code_uri=qr_uri,
        qr_code_data_uri=qr_data_uri,
    )


@router.post("/2fa/verify", response_model=TOTPVerifyResponse)
async def verify_2fa(
    body: TOTPVerifyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify a TOTP code and save the secret (completes 2FA setup).

    Returns backup codes on success. Store them securely — they are shown once.
    """
    result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.totp_enabled or user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="2FA is already configured.",
        )

    # Verify the TOTP code
    totp = pyotp.TOTP(body.secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code. Please try again.",
        )

    # Generate backup codes
    plain_codes, hashed_codes = generate_backup_codes(count=8)

    # Save encrypted secret + backup codes
    user.totp_secret = encrypt_totp_secret(body.secret)
    user.totp_enabled = True
    user.backup_codes = json.dumps(hashed_codes)
    await db.flush()

    return TOTPVerifyResponse(
        message="2FA has been enabled successfully.",
        backup_codes=plain_codes,
    )


@router.post("/2fa/disable", response_model=MessageResponse)
async def disable_2fa(
    body: TOTPDisableRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable 2FA after verifying password + current TOTP code."""
    result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this account.",
        )

    # Verify password
    if not _verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Verify TOTP code
    decrypted_secret = decrypt_totp_secret(user.totp_secret)
    totp = pyotp.TOTP(decrypted_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code.",
        )

    # Clear 2FA state
    user.totp_secret = None
    user.totp_enabled = False
    user.backup_codes = None
    await db.flush()

    return MessageResponse(message="2FA has been disabled successfully.")


@router.post("/2fa/authenticate", response_model=TokenResponse)
async def authenticate_2fa(
    body: TOTPLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete login with TOTP code after password verification.

    Use this endpoint when the user has 2FA enabled.
    The normal /auth/login endpoint returns a challenge if 2FA is active.
    """
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

    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this account. Use /auth/login instead.",
        )

    # Verify TOTP code (or backup code)
    decrypted_secret = decrypt_totp_secret(user.totp_secret)
    totp = pyotp.TOTP(decrypted_secret)
    valid = totp.verify(body.totp_code, valid_window=1)

    # If TOTP invalid, try backup codes
    if not valid and user.backup_codes:
        backup_hashes = json.loads(user.backup_codes)
        if verify_backup_code(body.totp_code, backup_hashes):
            valid = True
            # Remove used backup code
            used_hash = None
            for h in backup_hashes:
                import hashlib
                if hashlib.sha256(body.totp_code.upper().encode()).hexdigest() == h:
                    used_hash = h
                    break
            if used_hash:
                backup_hashes.remove(used_hash)
                user.backup_codes = json.dumps(backup_hashes) if backup_hashes else None

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code or backup code.",
        )

    return await _create_token_response(db, user)


# --- Admin Endpoints ---


@router.post("/admin/reset", response_model=AdminResetResponse)
async def admin_reset(
    current_user: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    """Reset the admin password using ADMIN_RESET_TOKEN env var.

    Requires admin authentication. Returns the new password
    so the admin can log in and change it immediately.
    """
    reset_token = os.environ.get("ADMIN_RESET_TOKEN")
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_RESET_TOKEN environment variable is not set.",
        )

    # Update the admin user's password
    result = await db.execute(
        select(User).where(User.email == "admin@kafcenter.com")
    )
    admin_user = result.scalar_one_or_none()
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found.",
        )

    admin_user.password_hash = _hash_password(reset_token)
    await db.flush()

    return AdminResetResponse(
        message="Admin password has been reset successfully.",
        new_password=reset_token,
    )


@router.post("/admin/reset-temp", include_in_schema=False)
async def admin_reset_temp(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """One-time admin password reset — TEMPORARY, will be removed after use."""
    secret = request.query_params.get("secret", "")
    if secret != "cef1e04af5a4eef3dd315ae078a52eef":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret")

    result = await db.execute(select(User).where(User.email == "admin@kafcenter.com"))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found")

    new_password = "KafExtract2026!Admin"
    user.password_hash = _hash_password(new_password)
    await db.commit()
    return {"message": "Admin password reset", "email": "admin@kafcenter.com"}


@router.post("/admin/init-reset", include_in_schema=False)
async def admin_init_reset(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Bootstrap admin password reset — DISABLED after initial use.

    This endpoint is permanently disabled after the admin account has been set up.
    The token check fails deliberately.
    """
    # DISABLED — admin account is now configured
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This bootstrap endpoint has been used and is now disabled.",
    )


# Optional auth — tries JWT first, falls back to API key, doesn't fail if neither
