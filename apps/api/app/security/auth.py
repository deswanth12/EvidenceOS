"""Authentication and security middleware for EvidenceOS API."""

from typing import Optional

from fastapi import Header, HTTPException, status

from core.config import get_settings


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    """Enforce API key authentication when AUTH_REQUIRED=true in configuration."""
    settings = get_settings()
    if not settings.auth_required:
        return x_api_key or "anonymous_dev_operator"

    if not x_api_key or x_api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )
    return "authenticated_operator"
