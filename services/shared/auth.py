"""
Kavalx JWT Authentication Utilities
=====================================

Provides JWT token creation and verification for inter-service and
client-to-gateway authentication.

Usage:
    from services.shared.auth import create_access_token, verify_token

    token = create_access_token(subject="user-123", scopes=["txn:read"])
    payload = verify_token(token)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from pydantic import BaseModel, Field

from services.shared.config import get_settings

logger = logging.getLogger(__name__)


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str = Field(..., description="Subject (user ID or service name).")
    scopes: List[str] = Field(default_factory=list, description="Granted scopes.")
    exp: datetime = Field(..., description="Expiration timestamp.")
    iat: datetime = Field(..., description="Issued-at timestamp.")
    jti: Optional[str] = Field(default=None, description="Unique token identifier.")


class AuthError(Exception):
    """Raised when token creation or verification fails."""

    def __init__(self, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def create_access_token(
    subject: str,
    scopes: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        subject: The ``sub`` claim – typically a user ID or service name.
        scopes: List of permission scopes (e.g. ``["txn:read", "txn:write"]``).
        expires_delta: Custom expiration delta.  Falls back to
            ``settings.jwt_expiry_minutes``.
        extra_claims: Additional claims merged into the payload.

    Returns:
        Encoded JWT string.

    Raises:
        AuthError: If token encoding fails.
    """
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_expiry_minutes)

    payload: Dict[str, Any] = {
        "sub": subject,
        "scopes": scopes or [],
        "iat": now,
        "exp": now + expires_delta,
    }

    if extra_claims:
        payload.update(extra_claims)

    try:
        token: str = jwt.encode(
            payload,
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        return token
    except Exception as exc:
        logger.exception("Failed to encode JWT for subject=%s", subject)
        raise AuthError(f"Token creation failed: {exc}") from exc


def verify_token(
    token: str,
    required_scopes: Optional[List[str]] = None,
) -> TokenPayload:
    """Decode and verify a JWT access token.

    Args:
        token: The raw JWT string.
        required_scopes: If provided, the token must contain **all** of these
            scopes; otherwise an ``AuthError`` is raised.

    Returns:
        Parsed ``TokenPayload``.

    Raises:
        AuthError: On expiration, invalid signature, or insufficient scopes.
    """
    settings = get_settings()

    try:
        raw: Dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired.", status_code=401)
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid token: {exc}", status_code=401)

    payload = TokenPayload(
        sub=raw["sub"],
        scopes=raw.get("scopes", []),
        exp=datetime.fromtimestamp(raw["exp"], tz=timezone.utc),
        iat=datetime.fromtimestamp(raw["iat"], tz=timezone.utc),
        jti=raw.get("jti"),
    )

    # Scope enforcement
    if required_scopes:
        granted = set(payload.scopes)
        missing = set(required_scopes) - granted
        if missing:
            raise AuthError(
                f"Insufficient scopes. Missing: {', '.join(sorted(missing))}",
                status_code=403,
            )

    return payload


def create_service_token(service_name: str) -> str:
    """Create a long-lived service-to-service JWT (24h).

    Args:
        service_name: Logical service name (e.g. ``"txn-intelligence"``).

    Returns:
        Encoded JWT string with ``service:*`` scope.
    """
    return create_access_token(
        subject=f"svc:{service_name}",
        scopes=["service:*"],
        expires_delta=timedelta(hours=24),
        extra_claims={"type": "service"},
    )
