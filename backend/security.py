from typing import Optional

from fastapi import Header, HTTPException, status

from config.settings import settings


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """
    Simple API key verification for extension and trusted clients.

    If EXTENSION_API_KEY is not configured, the check is a no-op so that
    local development remains frictionless. In any non-local environment,
    set EXTENSION_API_KEY to enforce authentication on all protected routes.
    """
    expected = settings.EXTENSION_API_KEY
    if not expected:
        # Auth disabled; accept all requests (development mode).
        return

    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )

