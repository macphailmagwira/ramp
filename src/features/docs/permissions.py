from fastapi import Depends, HTTPException
from uuid import UUID

from src.db.session import get_db_session
from src.features.docs.enums import ROLE_RANK, WorkspaceRole
from src.features.docs.repository import DocsRepository
from src.middleware.user_context import get_current_user


def require_workspace_role(min_role: WorkspaceRole):
    """Dependency factory: enforce that the caller has >= min_role in the workspace.

    401 (missing/invalid token) is already handled by UserContextMiddleware; this
    adds the per-workspace, per-user 403 check on top.
    """

    async def checker(
        workspace_id: UUID,
        user=Depends(get_current_user),
        db=Depends(get_db_session),
    ) -> WorkspaceRole:
        role = await DocsRepository(db).resolve_role(workspace_id, user.id)
        if role is None:
            raise HTTPException(status_code=403, detail="Not a member of this workspace")
        if ROLE_RANK[role] < ROLE_RANK[min_role]:
            raise HTTPException(status_code=403, detail="Insufficient role for this action")
        return role

    return checker
