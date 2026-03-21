"""
Authentication middleware for FastAPI routes.

This module provides dependency injection functions for protected routes,
Bearer token extraction, and role-based access control middleware.
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import settings
from .jwt_verifier import CognitoJWTVerifier

# Initialize HTTP Bearer security scheme
security = HTTPBearer()

# Initialize JWT verifier with Cognito configuration
jwt_verifier = CognitoJWTVerifier(
    region=settings.AWS_REGION,
    user_pool_id=settings.USER_POOL_ID,
    client_id=settings.USER_POOL_CLIENT_ID,
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """
    Dependency to get the current authenticated user from JWT token.

    Args:
        credentials: HTTP authorization credentials containing Bearer token

    Returns:
        Dictionary containing user information and claims

    Raises:
        HTTPException: If token is invalid or missing
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization credentials")

    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    # Verify token and extract claims
    decoded_token = jwt_verifier.verify_token(token)
    user_info = jwt_verifier.extract_user_info(decoded_token)

    return user_info


async def get_current_active_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Dependency to get the current active user (additional validation can be added).

    Args:
        current_user: User information from get_current_user

    Returns:
        Dictionary containing active user information

    Raises:
        HTTPException: If user is inactive or disabled
    """
    # Additional user status checks can be added here
    # For now, all authenticated users are considered active
    return current_user


def require_role(*allowed_roles: str):
    """
    Role-based access control decorator factory.

    Args:
        allowed_roles: List of roles that are allowed to access the endpoint

    Returns:
        Dependency function that checks user role

    Example:
        @app.get("/admin-only")
        async def admin_endpoint(user: dict = Depends(require_role("admin"))):
            return {"message": "Admin access granted"}
    """

    def role_checker(current_user: dict = Depends(get_current_active_user)) -> dict:
        user_role = current_user.get("role")

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}. "
                f"User role: {user_role}",
            )

        return current_user

    return role_checker


def require_admin():
    """
    Convenience function for admin-only access.

    Returns:
        Dependency function that requires admin role
    """
    return require_role("admin")


def require_supervisor_or_admin():
    """
    Convenience function for supervisor or admin access.

    Returns:
        Dependency function that requires supervisor or admin role
    """
    return require_role("supervisor", "admin")


def require_group(*required_groups: str):
    """
    Group-based access control decorator factory.

    Args:
        required_groups: List of Cognito groups required to access the endpoint

    Returns:
        Dependency function that checks user groups

    Example:
        @app.get("/managers-only")
        async def managers_endpoint(user: dict = Depends(require_group("managers", "admin"))):
            return {"message": "Manager access granted"}
    """

    def group_checker(current_user: dict = Depends(get_current_active_user)) -> dict:
        user_groups = current_user.get("groups", [])

        # Check if user has any of the required groups
        has_required_group = any(group in user_groups for group in required_groups)

        if not has_required_group:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required groups: {', '.join(required_groups)}. "
                f"User groups: {', '.join(user_groups)}",
            )

        return current_user

    return group_checker


async def get_optional_user(request: Request) -> Optional[dict]:
    """
    Optional authentication dependency that doesn't raise errors.

    Useful for endpoints that can work with or without authentication,
    providing additional features for authenticated users.

    Args:
        request: FastAPI request object

    Returns:
        User information if token is valid, None otherwise
    """
    authorization = request.headers.get("Authorization")

    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        token = authorization.split(" ", 1)[1]
        decoded_token = jwt_verifier.verify_token(token)
        user_info = jwt_verifier.extract_user_info(decoded_token)
        return user_info
    except (HTTPException, IndexError):
        # Token is invalid, expired, or malformed, but we don't raise an error
        return None


# Common dependency aliases for convenience
RequireAuth = Depends(get_current_active_user)
RequireAdmin = Depends(require_admin())
RequireSupervisorOrAdmin = Depends(require_supervisor_or_admin())
OptionalAuth = Depends(get_optional_user)
