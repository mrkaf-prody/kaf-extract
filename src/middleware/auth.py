"""Auth middleware — JWT dependency injection for FastAPI."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db

# Security scheme for Swagger UI
security_scheme = HTTPBearer(
    scheme_name="JWT",
    description="Enter JWT token from /auth/login",
    auto_error=True,
)


def create_access_token(user_id: str, email: str, role: str) -> str:
    """Create a JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token (longer-lived)."""
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dependency: extract and validate the JWT from the Authorization header.

    Returns a dict with keys: user_id (UUID), email, role.
    """
    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an access token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    # Verify user exists and is active
    from src.models.sql_models import User
    result = await db.execute(
        select(User).where(User.id == UUID(user_id), User.status == "active")
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return {
        "user_id": UUID(user_id),
        "email": payload["email"],
        "role": payload["role"],
    }


async def admin_required(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Dependency: require admin role."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# Optional auth — tries JWT first, falls back to API key, doesn't fail if neither
async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """Dependency: optional user extraction (JWT or API key). Returns None if no auth."""
    # Try JWT first
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("type") == "access" and payload.get("sub"):
                from src.models.sql_models import User
                result = await db.execute(
                    select(User).where(
                        User.id == UUID(payload["sub"]), User.status == "active"
                    )
                )
                user = result.scalar_one_or_none()
                if user:
                    return {
                        "user_id": UUID(payload["sub"]),
                        "email": payload["email"],
                        "role": payload["role"],
                    }
        except (JWTError, ValueError):
            pass

    # Fall back to API key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        from src.models.apikey import verify_api_key as verify_apikey_async
        key_info = await verify_apikey_async(api_key)
        if key_info:
            return key_info

    return None
