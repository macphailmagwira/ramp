"""Business logic for the docs/workspaces feature.

The critical method is `save_content`: it performs a version-checked, row-locked
write so that out-of-order or concurrent saves from the frontend cannot clobber
each other. A mismatch returns a VersionConflict (409).
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import select

from src.common.base_repository import BaseRepository
from src.features.docs.enums import WorkspaceRole
from src.features.docs.exceptions import VersionConflict
from src.features.docs.models import Node, Workspace
from src.features.docs.repository import DocsRepository
from src.features.docs.schema import (
    ContentResponse,
    DocBlock,
    KnowledgeNode,
    PutContentRequest,
    VersionDetail,
    VersionSummary,
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from src.features.user.models import User


class DocsService(BaseRepository):
    # ---------- workspaces ----------
    async def create_workspace(
        self,
        owner_id: uuid.UUID,
        account_id: uuid.UUID,
        payload: WorkspaceCreate,
        connected_repository_id: uuid.UUID | None = None,
    ) -> WorkspaceResponse:
        repo = DocsRepository(self.db)
        ws = await repo.create_workspace(
            owner_id,
            account_id,
            payload.label,
            payload.icon,
            payload.repo,
            connected_repository_id,
        )
        await self.db.commit()
        await self.db.refresh(ws)
        return _workspace_response(ws, WorkspaceRole.OWNER)

    async def list_workspaces(
        self, user_id: uuid.UUID, account_id: uuid.UUID, repo: str | None = None
    ) -> list[WorkspaceResponse]:
        repo_ = DocsRepository(self.db)
        wss = await repo_.list_workspaces(account_id, repo)
        out = []
        for ws in wss:
            role = await repo_.resolve_role(ws.id, user_id, account_id) or WorkspaceRole.EDITOR
            out.append(_workspace_response(ws, role))
        return out

    async def list_shared_nodes(self, account_id: uuid.UUID) -> list[KnowledgeNode]:
        repo = DocsRepository(self.db)
        return [_node_response(n) for n in await repo.list_shared_nodes(account_id)]

    async def update_workspace(
        self, ws_id: uuid.UUID, user_id: uuid.UUID, account_id: uuid.UUID, payload: WorkspaceUpdate
    ) -> WorkspaceResponse:
        repo = DocsRepository(self.db)
        ws = await self._require_workspace(repo, ws_id, user_id, account_id)
        ws = await repo.update_workspace(ws, payload.label, payload.icon, payload.repo)
        await self.db.commit()
        await self.db.refresh(ws)
        return _workspace_response(ws, WorkspaceRole.OWNER)

    async def delete_workspace(self, ws_id: uuid.UUID, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
        repo = DocsRepository(self.db)
        ws = await self._require_workspace(repo, ws_id, user_id, account_id)
        if ws.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Only the workspace owner can delete it")
        await repo.delete_workspace(ws_id)
        await self.db.commit()

    # ---------- members ----------
    async def list_members(self, ws_id: uuid.UUID) -> list[WorkspaceMemberResponse]:
        repo = DocsRepository(self.db)
        rows = await repo.list_members(ws_id)
        return [
            WorkspaceMemberResponse(
                user_id=m.user_id,
                name=(u.first_name + " " + u.last_name).strip() if u else None,
                email=u.email if u else None,
                avatar=None,
                role=m.role.value,
                added_at=m.added_at,
            )
            for m, u in rows
        ]

    async def add_member(self, ws_id: uuid.UUID, payload: WorkspaceMemberCreate) -> WorkspaceMemberResponse:
        repo = DocsRepository(self.db)
        user_id = payload.user_id
        if user_id is None and payload.email:
            user = await repo.get_user_by_email(payload.email)
            if user is None:
                raise HTTPException(status_code=404, detail="User with that email not found")
            user_id = user.id
        if await repo.get_member(ws_id, user_id):
            raise HTTPException(status_code=409, detail="User is already a member")
        m = await repo.add_member(ws_id, user_id, payload.role)
        await self.db.commit()
        await self.db.refresh(m)
        user = await _get_user(self.db, user_id)
        return _member_response(m, user)

    async def set_member_role(
        self, ws_id: uuid.UUID, member_user_id: uuid.UUID, role: WorkspaceRole
    ) -> WorkspaceMemberResponse:
        repo = DocsRepository(self.db)
        m = await repo.get_member(ws_id, member_user_id)
        if m is None:
            raise HTTPException(status_code=404, detail="Member not found")
        m = await repo.set_member_role(m, role)
        await self.db.commit()
        await self.db.refresh(m)
        user = await _get_user(self.db, member_user_id)
        return _member_response(m, user)

    async def remove_member(self, ws_id: uuid.UUID, member_user_id: uuid.UUID) -> None:
        repo = DocsRepository(self.db)
        ws = await repo.get_workspace(ws_id)
        if ws is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if ws.owner_id == member_user_id:
            raise HTTPException(status_code=400, detail="Cannot remove the workspace owner")
        await repo.remove_member(ws_id, member_user_id)
        await self.db.commit()

    # ---------- nodes ----------
    async def create_node(
        self, ws_id: uuid.UUID, user_id: uuid.UUID, parent_id, ntype, label, title=None, shared=False
    ) -> KnowledgeNode:
        repo = DocsRepository(self.db)
        if parent_id is not None:
            parent = await repo.get_node(parent_id)
            if parent is None or parent.workspace_id != ws_id:
                raise HTTPException(status_code=400, detail="Invalid parent_id")
        node = await repo.create_node(
            ws_id, parent_id, ntype, label, title if title is not None else "Title", shared
        )
        await self.db.commit()
        await self.db.refresh(node)
        return _node_response(node)

    async def list_nodes(self, ws_id: uuid.UUID, account_id: uuid.UUID) -> list[KnowledgeNode]:
        repo = DocsRepository(self.db)
        return [_node_response(n) for n in await repo.list_nodes(ws_id, account_id)]

    async def rename_node(
        self,
        ws_id: uuid.UUID,
        node_id: uuid.UUID,
        label: str | None = None,
        title: str | None = None,
        shared: bool | None = None,
    ) -> KnowledgeNode:
        repo = DocsRepository(self.db)
        node = await self._require_node(repo, ws_id, node_id)
        node = await repo.rename_node(node, label, title)
        if shared is not None:
            node = await repo.set_shared(node, shared)
        await self.db.commit()
        await self.db.refresh(node)
        return _node_response(node)

    async def delete_node(self, ws_id: uuid.UUID, node_id: uuid.UUID) -> None:
        repo = DocsRepository(self.db)
        await self._require_node(repo, ws_id, node_id)
        await repo.delete_node(node_id)
        await self.db.commit()

    async def share_node(self, ws_id: uuid.UUID, node_id: uuid.UUID, shared: bool) -> KnowledgeNode:
        # Only the owning workspace may change a node's shared flag.
        repo = DocsRepository(self.db)
        node = await self._require_node(repo, ws_id, node_id)
        node = await repo.set_shared(node, shared)
        await self.db.commit()
        await self.db.refresh(node)
        return _node_response(node)

    async def move_node(
        self, ws_id: uuid.UUID, node_id: uuid.UUID, new_parent_id: uuid.UUID | None
    ) -> KnowledgeNode:
        repo = DocsRepository(self.db)
        node = await self._require_node(repo, ws_id, node_id)
        if new_parent_id is not None:
            if new_parent_id == node_id:
                raise HTTPException(status_code=400, detail="Cannot move a node into itself")
            parent = await repo.get_node(new_parent_id)
            if parent is None or parent.workspace_id != ws_id:
                raise HTTPException(status_code=400, detail="Invalid new_parent_id")
            descendants = await repo.get_descendant_ids(node_id)
            if new_parent_id in descendants:
                raise HTTPException(status_code=400, detail="Cannot move a node into its own subtree")
        node = await repo.set_parent(node, new_parent_id)
        await self.db.commit()
        await self.db.refresh(node)
        return _node_response(node)

    # ---------- content + versions ----------
    async def get_content(self, ws_id: uuid.UUID, node_id: uuid.UUID) -> ContentResponse:
        repo = DocsRepository(self.db)
        await self._require_node(repo, ws_id, node_id, allow_shared=True)
        content = await repo.get_content(node_id)
        if content is None:
            raise HTTPException(status_code=404, detail="Content not found")
        node = await repo.get_node(node_id)
        return ContentResponse(
            id=node_id,
            label=content.label,
            blocks=[DocBlock(**b) for b in content.blocks],
            version=node.version,
            updated_at=content.updated_at,
        )

    async def save_content(
        self,
        ws_id: uuid.UUID,
        node_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: PutContentRequest,
    ) -> ContentResponse:
        repo = DocsRepository(self.db)
        node = await repo.get_node_locked(node_id)
        if node is None or node.workspace_id != ws_id:
            raise HTTPException(status_code=404, detail="Node not found")

        blocks_data = [b.model_dump() for b in payload.blocks]
        label = payload.label if payload.label is not None else node.label

        if payload.base_version is None:
            if node.version == 0 and not await repo.content_exists(node_id):
                new_version = 1
            else:
                new_version = node.version + 1
        elif payload.base_version == node.version:
            new_version = node.version + 1
        else:
            cur = await repo.get_content(node_id)
            raise VersionConflict(
                version=node.version,
                blocks=cur.blocks if cur else [],
                label=cur.label if cur else node.label,
            )

        node.version = new_version
        node.updated_by = user_id
        await repo.upsert_content(node_id, label, blocks_data)
        await repo.insert_version(node_id, new_version, label, blocks_data, user_id)
        await self.db.commit()
        content = await repo.get_content(node_id)
        return ContentResponse(
            id=node_id,
            label=label,
            blocks=payload.blocks,
            version=new_version,
            updated_at=content.updated_at if content else node.updated_at,
        )

    async def list_versions(self, ws_id: uuid.UUID, node_id: uuid.UUID) -> list[VersionSummary]:
        repo = DocsRepository(self.db)
        await self._require_node(repo, ws_id, node_id, allow_shared=True)
        versions = await repo.list_versions(node_id)
        return [
            VersionSummary(
                version=v.version,
                label=v.label,
                block_count=len(v.blocks or []),
                edited_by=v.edited_by,
                created_at=v.created_at,
            )
            for v in versions
        ]

    async def get_version(
        self, ws_id: uuid.UUID, node_id: uuid.UUID, version: int
    ) -> VersionDetail:
        repo = DocsRepository(self.db)
        await self._require_node(repo, ws_id, node_id, allow_shared=True)
        v = await repo.get_version(node_id, version)
        if v is None:
            raise HTTPException(status_code=404, detail="Version not found")
        return VersionDetail(label=v.label, blocks=[DocBlock(**b) for b in v.blocks])

    async def restore_version(
        self, ws_id: uuid.UUID, node_id: uuid.UUID, version: int, user_id: uuid.UUID
    ) -> dict:
        repo = DocsRepository(self.db)
        node = await repo.get_node_locked(node_id)
        if node is None or node.workspace_id != ws_id:
            raise HTTPException(status_code=404, detail="Node not found")
        snap = await repo.get_version(node_id, version)
        if snap is None:
            raise HTTPException(status_code=404, detail="Version not found")
        new_version = node.version + 1
        node.version = new_version
        node.updated_by = user_id
        await repo.upsert_content(node_id, snap.label, snap.blocks)
        await repo.insert_version(node_id, new_version, snap.label, snap.blocks, user_id)
        await self.db.commit()
        return {"version": new_version}

    # ---------- helpers ----------
    async def _require_workspace(
        self, repo: DocsRepository, ws_id: uuid.UUID, user_id: uuid.UUID, account_id: uuid.UUID
    ) -> Workspace:
        ws = await repo.get_workspace(ws_id)
        if ws is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        role = await repo.resolve_role(ws_id, user_id, account_id)
        if role is None:
            raise HTTPException(status_code=403, detail="Not a member of this workspace")
        return ws

    async def _require_node(
        self, repo: DocsRepository, ws_id: uuid.UUID, node_id: uuid.UUID, allow_shared: bool = False
    ) -> Node:
        node = await repo.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="Node not found")
        if node.workspace_id == ws_id:
            return node
        # Shared nodes are readable across workspaces in the same account only.
        if not (allow_shared and node.shared):
            raise HTTPException(status_code=404, detail="Node not found")
        caller_ws = await repo.get_workspace(ws_id)
        owner_ws = await repo.get_workspace(node.workspace_id)
        if (
            caller_ws is None
            or owner_ws is None
            or caller_ws.account_id != owner_ws.account_id
        ):
            raise HTTPException(status_code=404, detail="Node not found")
        return node


# ---------- response builders ----------
async def _get_user(db, user_id: uuid.UUID) -> User | None:
    return (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()


def _member_response(m, user: User | None) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        user_id=m.user_id,
        name=(user.first_name + " " + user.last_name).strip() if user else None,
        email=user.email if user else None,
        avatar=None,
        role=m.role.value,
        added_at=m.added_at,
    )


def _workspace_response(ws: Workspace, role: WorkspaceRole) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=ws.id,
        owner_id=ws.owner_id,
        label=ws.label,
        icon=ws.icon,
        role=role.value,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


def _node_response(node: Node) -> KnowledgeNode:
    return KnowledgeNode(
        id=node.id,
        workspace_id=node.workspace_id,
        parent_id=node.parent_id,
        type=node.type.value if hasattr(node.type, "value") else node.type,
        label=node.label,
        title=node.title,
        version=node.version,
        shared=node.shared,
        updated_at=node.updated_at,
        updated_by=node.updated_by,
    )
