"""API Key model and utilities."""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory API key store for MVP
# Format: {hashed_key: {"label": "dev-key", "rate_limit": 100}}
_api_keys: dict[str, dict] = {}

# Dev key: hashed version of the default dev key
_default_key = "kaf-extract-dev-key-change-in-production"
_api_keys[pwd_context.hash(_default_key)] = {"label": "dev-default", "rate_limit": 100}


def verify_api_key(key: str) -> dict | None:
    """Verify an API key and return its metadata, or None."""
    for hashed, meta in _api_keys.items():
        if pwd_context.verify(key, hashed):
            return meta
    return None


def get_api_key_info(key: str) -> dict | None:
    """Get metadata for an API key without re-hashing (use after verify)."""
    return verify_api_key(key)
