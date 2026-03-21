# Authentication System

This directory contains the JWT authentication system for AWS Cognito integration.

## Overview

The authentication system provides:

- JWT token verification using AWS Cognito public keys
- Role-based access control (admin, supervisor, operator)
- Group-based access control using Cognito groups
- Dependency injection for protected routes
- Optional authentication for flexible endpoints

## Configuration

Set these environment variables:

```bash
# Required for JWT verification
USER_POOL_CLIENT_ID=your_cognito_client_id

# These are already configured in base_config.py:
# AWS_REGION=ap-southeast-1
# USER_POOL_ID=ap-southeast-1_P9lB7c3WV
```

## Usage Examples

### Basic Protected Endpoint

```python
from fastapi import Depends
from .auth.auth_middleware import get_current_user

@app.get("/protected")
async def protected_route(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}
```

### Role-Based Access Control

```python
from .auth.auth_middleware import RequireAdmin, require_role

# Admin only
@app.get("/admin")
async def admin_route(current_user: dict = RequireAdmin):
    return {"message": "Admin access"}

# Multiple roles
@app.get("/management")
async def management_route(current_user: dict = Depends(require_role("supervisor", "admin"))):
    return {"message": "Management access"}
```

### Group-Based Access Control

```python
from .auth.auth_middleware import require_group

@app.get("/special-group")
async def special_route(current_user: dict = Depends(require_group("special_group", "admin"))):
    return {"message": "Special group access"}
```

### Optional Authentication

```python
from .auth.auth_middleware import OptionalAuth

@app.get("/optional")
async def optional_route(current_user: Optional[dict] = OptionalAuth):
    if current_user:
        return {"message": f"Hello {current_user['email']}"}
    return {"message": "Hello anonymous user"}
```

## User Object Structure

The `current_user` object contains:

```python
{
    "id": "cognito_sub",           # Unique user ID
    "email": "user@example.com",   # User email
    "username": "username",        # Username (if available)
    "groups": ["admin", "users"],  # Cognito groups
    "role": "admin",              # Mapped role (admin/supervisor/operator)
    "token_use": "access",        # Token type
    "exp": 1640995200,            # Expiration timestamp
    "iat": 1640991600             # Issued at timestamp
}
```

## Role Mapping

- `admin` role: Users in "admin" Cognito group
- `supervisor` role: Users in "supervisor" Cognito group
- `operator` role: Default role for all other users

## Testing

Use the example endpoints in `main.py` to test authentication:

- `GET /api/protected` - Requires any valid token
- `GET /api/admin-only` - Requires admin role
- `GET /api/supervisor-or-admin` - Requires supervisor or admin role
- `GET /api/optional-auth` - Works with or without token

## Error Handling

The system returns appropriate HTTP status codes:

- `401 Unauthorized` - Missing, invalid, or expired token
- `403 Forbidden` - Valid token but insufficient permissions
- `500 Internal Server Error` - System errors (JWKS fetch failed, etc.)
