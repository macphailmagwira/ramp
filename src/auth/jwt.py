"""Local JWT utilities for the username/password auth flow.

These tokens are signed with the application SECRET_KEY (HS256) and carry the
user id in the ``sub`` claim so the request middleware can resolve the logged-in
user without depending on an external identity provider.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt

from src.config import settings


def create_access_token(
    subject: str,
    email: Optional[str] = None,
    expires_minutes: Optional[int] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed access token for the given user.

    Args:
        subject: The user id (used as the ``sub`` claim).
        email: Optional email claim for convenience.
        expires_minutes: Override for the token lifetime in minutes.
        extra_claims: Additional claims to embed in the token.

    Returns:
        The encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    if email is not None:
        to_encode["email"] = email
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and verify an access token.

    Raises:
        JWTError: If the token is invalid, expired, or fails signature checks.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_exp": True},
    )
