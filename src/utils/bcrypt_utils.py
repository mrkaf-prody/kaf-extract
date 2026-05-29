"""Centralized bcrypt utilities — replaces passlib.

Bcrypt truncates inputs at 72 bytes silently. For long strings
(refresh tokens, API keys, passwords), we SHA-256 before bcrypt.

All hashing uses bcrypt rounds=12.
"""

import hashlib

import bcrypt

_ROUNDS = 12


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (passwords are typically < 72 bytes)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _sha256(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def hash_token(raw: str) -> str:
    """Hash a long token/key with SHA-256 + bcrypt to avoid 72-byte truncation."""
    digest = _sha256(raw)
    return bcrypt.hashpw(digest, bcrypt.gensalt(rounds=_ROUNDS)).decode("utf-8")


def verify_token(raw: str, hashed: str) -> bool:
    """Verify a long token/key against its SHA-256 + bcrypt hash."""
    digest = _sha256(raw)
    return bcrypt.checkpw(digest, hashed.encode("utf-8"))
