import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.features.docs.enums import WorkspaceRole
from src.features.docs.permissions import require_workspace_role
from src.features.docs.schema import (
    ContentResponse,
    MoveRequest,
    NodeCreate,
    NodeRename,
    PutContentRequest,
    VersionDetail,
    VersionSummary,
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from src.features.docs.service import DocsService
from src.middleware.user_context import EnrichedUserContext, get_current_user


logger = logging.getLogger("api-main.docs.router")

docs_router = APIRouter(prefix="/workspaces", tags=["docs"])


# ---------------- workspaces ----------------
@docs_router.get("")
async def list_workspaces(
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[WorkspaceResponse]:
    return await DocsService(db).list_workspaces(user.id)


@docs_router.post("")
async def create_workspace(
    payload: WorkspaceCreate,
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WorkspaceResponse:
    return await DocsService(db).create_workspace(user.id, payload)


@docs_router.patch(
    "/{workspace_id}",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdate,
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WorkspaceResponse:
    return await DocsService(db).update_workspace(workspace_id, user.id, payload)


@docs_router.delete(
    "/{workspace_id}",
    status_code=204,
    dependencies=[Depends(require_workspace_role(WorkspaceRole.OWNER))],
)
async def delete_workspace(
    workspace_id: UUID,
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    await DocsService(db).delete_workspace(workspace_id, user.id)


# ---------------- members ----------------
@docs_router.get(
    "/{workspace_id}/members",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.VIEWER))],
)
async def list_members(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[WorkspaceMemberResponse]:
    return await DocsService(db).list_members(workspace_id)


@docs_router.post(
    "/{workspace_id}/members",
    status_code=201,
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def add_member(
    workspace_id: UUID,
    payload: WorkspaceMemberCreate,
    db: AsyncSession = Depends(get_db_session),
) -> WorkspaceMemberResponse:
    return await DocsService(db).add_member(workspace_id, payload)


@docs_router.patch(
    "/{workspace_id}/members/{user_id}",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def set_member_role(
    workspace_id: UUID,
    user_id: UUID,
    payload: WorkspaceMemberCreate,
    db: AsyncSession = Depends(get_db_session),
) -> WorkspaceMemberResponse:
    return await DocsService(db).set_member_role(workspace_id, user_id, payload.role)


@docs_router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=204,
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def remove_member(
    workspace_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    await DocsService(db).remove_member(workspace_id, user_id)


# ---------------- nodes (tree) ----------------
@docs_router.get(
    "/{workspace_id}/nodes",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.VIEWER))],
)
async def list_nodes(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    return await DocsService(db).list_nodes(workspace_id)


@docs_router.post(
    "/{workspace_id}/nodes",
    status_code=201,
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def create_node(
    workspace_id: UUID,
    payload: NodeCreate,
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await DocsService(db).create_node(
        workspace_id, user.id, payload.parent_id, payload.type.value, payload.label
    )


@docs_router.patch(
    "/{workspace_id}/nodes/{node_id}",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def rename_node(
    workspace_id: UUID,
    node_id: UUID,
    payload: NodeRename,
    db: AsyncSession = Depends(get_db_session),
):
    return await DocsService(db).rename_node(workspace_id, node_id, payload.label)


@docs_router.delete(
    "/{workspace_id}/nodes/{node_id}",
    status_code=204,
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def delete_node(
    workspace_id: UUID,
    node_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    await DocsService(db).delete_node(workspace_id, node_id)


@docs_router.post(
    "/{workspace_id}/nodes/{node_id}/move",
    status_code=204,
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def move_node(
    workspace_id: UUID,
    node_id: UUID,
    payload: MoveRequest,
    db: AsyncSession = Depends(get_db_session),
):
    await DocsService(db).move_node(workspace_id, node_id, payload.new_parent_id)


# ---------------- content + versions ----------------
@docs_router.get(
    "/{workspace_id}/nodes/{node_id}/content",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.VIEWER))],
)
async def get_content(
    workspace_id: UUID,
    node_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ContentResponse:
    return await DocsService(db).get_content(workspace_id, node_id)


@docs_router.put(
    "/{workspace_id}/nodes/{node_id}/content",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def put_content(
    workspace_id: UUID,
    node_id: UUID,
    payload: PutContentRequest,
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ContentResponse:
    return await DocsService(db).save_content(
        workspace_id, node_id, user.id, payload
    )


@docs_router.get(
    "/{workspace_id}/nodes/{node_id}/versions",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.VIEWER))],
)
async def list_versions(
    workspace_id: UUID,
    node_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[VersionSummary]:
    return await DocsService(db).list_versions(workspace_id, node_id)


@docs_router.get(
    "/{workspace_id}/nodes/{node_id}/versions/{version}",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.VIEWER))],
)
async def get_version(
    workspace_id: UUID,
    node_id: UUID,
    version: int,
    db: AsyncSession = Depends(get_db_session),
) -> VersionDetail:
    return await DocsService(db).get_version(workspace_id, node_id, version)


@docs_router.post(
    "/{workspace_id}/nodes/{node_id}/versions/{version}/restore",
    dependencies=[Depends(require_workspace_role(WorkspaceRole.EDITOR))],
)
async def restore_version(
    workspace_id: UUID,
    node_id: UUID,
    version: int,
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await DocsService(db).restore_version(
        workspace_id, node_id, version, user.id
    )
