"""Encryption utilities for TOTP secrets and backup codes."""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Sequence

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.config import settings


def _get_fernet() -> Fernet:
    """Derive Fernet key from JWT secret so we don't need another env var."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"kaf-extract-totp-salt-v1",
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.jwt_secret.encode()))
    return Fernet(key)


def encrypt_totp_secret(plain_secret: str) -> str:
    """Encrypt a raw TOTP secret for DB storage."""
    return _get_fernet().encrypt(plain_secret.encode()).decode()


def decrypt_totp_secret(encrypted_secret: str) -> str:
    """Decrypt a stored TOTP secret."""
    return _get_fernet().decrypt(encrypted_secret.encode()).decode()


def generate_backup_codes(count: int = 8) -> tuple[list[str], list[str]]:
    """Generate human-readable backup codes.

    Returns (plain_codes, hashed_codes).
    """
    plain = []
    hashed = []
    for _ in range(count):
        code = secrets.token_hex(4).upper()
        plain.append(code)
        hashed.append(hashlib.sha256(code.encode()).hexdigest())
    return plain, hashed


def verify_backup_code(code: str, hashed_codes: Sequence[str]) -> bool:
    """Check if a plain backup code matches any stored hash."""
    code_hash = hashlib.sha256(code.upper().encode()).hexdigest()
    return code_hash in hashed_codes
