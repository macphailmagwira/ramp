from datetime import datetime
from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from src.auth.permissions import require_group
from src.middleware.user_context import get_current_user

from src.middleware.rate_limit import limiter


router = APIRouter()


# Public health endpoint
@router.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "api-main",
        "version": "0.1.0",
        "environment": "DEV",
    }


# Protected route: any authenticated user
@router.get("/protected")
async def protected_route(user = Depends(get_current_user)):
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "tenant": {
            "id": str(user.tenant_id),
            "name": user.db_user.tenant.name if user.db_user.tenant else None
        },
        "factory": {
            "id": str(user.factory_id),
            "name": user.db_user.factory.name if user.db_user.factory else None
        },
        "roles": [
            {
                "role": role.role.value,
                "department": role.department.value if role.department else None,
                "factory": role.factory.name if role.factory else None,
                "lines": [line.name for line in role.lines],
                "sectors": [sector.name for sector in role.sectors],
            }
            for role in user.user_roles
        ]
    }


# Protected route: only users in a specific group
@router.get("/admin-only")
async def admin_route(user = Depends(require_group("SuperAdmin"))):
    return {
        "message": "You are an admin!",
        "user": user,
        "timestamp": datetime.now().isoformat(),
    }

