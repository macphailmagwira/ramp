"""Repository (DB access) for the docs/workspaces feature."""

import uuid

from sqlalchemy import delete, select

from src.common.base_repository import BaseRepository
from src.features.docs.enums import NodeType, WorkspaceRole
from src.features.docs.models import (
    DocVersion,
    Node,
    NodeContent,
    Workspace,
    WorkspaceMember,
)
from src.features.user.models import User

DEFAULT_WORKSPACE_LABEL = "Engineering"
DEFAULT_WORKSPACE_ICON = "⚙️"

DEFAULT_FOLDER_LABELS = (
    "Product Requirements",
    "Technical Designs",
    "Implementation Plans",
    "Testing & QA",
    "Engineering Decisions",
    "Releases",
)


class DocsRepository(BaseRepository):
    # ---- workspaces ----
    async def create_workspace(
        self,
        owner_id: uuid.UUID,
        account_id: uuid.UUID,
        label: str,
        icon: str | None,
        repo: str | None = None,
        connected_repository_id: uuid.UUID | None = None,
    ) -> Workspace:
        ws = Workspace(
            owner_id=owner_id,
            account_id=account_id,
            label=label,
            icon=icon,
            repo=repo,
            connected_repository_id=connected_repository_id,
        )
        self.db.add(ws)
        await self.db.flush()
        self.db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner_id, role=WorkspaceRole.OWNER))
        await self.db.flush()
        await self._create_default_folders(ws.id)
        return ws

    async def _create_default_folders(self, ws_id: uuid.UUID) -> None:
        self.db.add_all(
            Node(
                workspace_id=ws_id,
                parent_id=None,
                type=NodeType.FOLDER,
                label=label,
                title=label,
            )
            for label in DEFAULT_FOLDER_LABELS
        )
        await self.db.flush()

    async def get_workspace(self, ws_id: uuid.UUID) -> Workspace | None:
        return (
            await self.db.execute(select(Workspace).where(Workspace.id == ws_id))
        ).scalar_one_or_none()

    async def get_workspace_for_repo(
        self, connected_repository_id: uuid.UUID
    ) -> Workspace | None:
        return (
            await self.db.execute(
                select(Workspace).where(
                    Workspace.connected_repository_id == connected_repository_id
                )
            )
        ).scalar_one_or_none()

    async def list_workspaces(
        self, account_id: uuid.UUID, repo: str | None = None
    ) -> list[Workspace]:
        cond = [Workspace.account_id == account_id]
        if repo is not None:
            cond.append(Workspace.repo == repo)
        return list((await self.db.execute(select(Workspace).where(*cond))).scalars().all())

    async def update_workspace(
        self, ws: Workspace, label: str | None, icon: str | None, repo: str | None = None
    ) -> Workspace:
        if label is not None:
            ws.label = label
        if icon is not None:
            ws.icon = icon
        if repo is not None:
            ws.repo = repo
        await self.db.flush()
        return ws

    async def delete_workspace(self, ws_id: uuid.UUID) -> None:
        await self.db.execute(delete(Workspace).where(Workspace.id == ws_id))

    # ---- members ----
    async def list_members(self, ws_id: uuid.UUID) -> list[tuple[WorkspaceMember, User | None]]:
        res = await self.db.execute(
            select(WorkspaceMember, User)
            .outerjoin(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == ws_id)
        )
        return list(res.all())

    async def get_member(self, ws_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember | None:
        return (
            await self.db.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == ws_id, WorkspaceMember.user_id == user_id
                )
            )
        ).scalar_one_or_none()

    async def add_member(self, ws_id: uuid.UUID, user_id: uuid.UUID, role: WorkspaceRole) -> WorkspaceMember:
        m = WorkspaceMember(workspace_id=ws_id, user_id=user_id, role=role)
        self.db.add(m)
        await self.db.flush()
        return m

    async def set_member_role(self, member: WorkspaceMember, role: WorkspaceRole) -> WorkspaceMember:
        member.role = role
        await self.db.flush()
        return member

    async def remove_member(self, ws_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.db.execute(
            delete(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws_id, WorkspaceMember.user_id == user_id
            )
        )

    async def resolve_role(
        self, ws_id: uuid.UUID, user_id: uuid.UUID, account_id: uuid.UUID | None = None
    ) -> WorkspaceRole | None:
        ws = await self.get_workspace(ws_id)
        if ws is None:
            return None
        if ws.owner_id == user_id:
            return WorkspaceRole.OWNER
        member = await self.get_member(ws_id, user_id)
        if member:
            return member.role
        if account_id is not None and ws.account_id == account_id:
            return WorkspaceRole.EDITOR
        return None

    async def get_user_by_email(self, email: str) -> User | None:
        return (
            await self.db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    # ---- nodes ----
    async def create_node(
        self,
        ws_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        type: str,
        label: str,
        title: str,
        shared: bool = False,
    ) -> Node:
        node = Node(
            workspace_id=ws_id,
            parent_id=parent_id,
            type=type,
            label=label,
            title=title,
            shared=shared,
        )
        self.db.add(node)
        await self.db.flush()
        return node

    async def list_nodes(self, ws_id: uuid.UUID, account_id: uuid.UUID) -> list[Node]:
        # Own nodes plus shared nodes from other workspaces in the same account.
        return list(
            (
                await self.db.execute(
                    select(Node)
                    .join(Workspace, Workspace.id == Node.workspace_id)
                    .where(
                        (Node.workspace_id == ws_id)
                        | ((Node.shared == True) & (Workspace.account_id == account_id))  # noqa: E712
                    )
                )
            ).scalars().all()
        )

    async def list_shared_nodes(self, account_id: uuid.UUID) -> list[Node]:
        return list(
            (
                await self.db.execute(
                    select(Node)
                    .join(Workspace, Workspace.id == Node.workspace_id)
                    .where(
                        Node.shared == True,  # noqa: E712
                        Workspace.account_id == account_id,
                    )
                )
            ).scalars().all()
        )

    async def get_node(self, node_id: uuid.UUID) -> Node | None:
        return (
            await self.db.execute(select(Node).where(Node.id == node_id))
        ).scalar_one_or_none()

    async def get_node_locked(self, node_id: uuid.UUID) -> Node | None:
        return (
            await self.db.execute(
                select(Node).where(Node.id == node_id).with_for_update()
            )
        ).scalar_one_or_none()

    async def rename_node(
        self, node: Node, label: str | None = None, title: str | None = None
    ) -> Node:
        if label is not None:
            node.label = label
        if title is not None:
            node.title = title
        await self.db.flush()
        return node

    async def set_parent(self, node: Node, parent_id: uuid.UUID | None) -> Node:
        node.parent_id = parent_id
        await self.db.flush()
        return node

    async def set_shared(self, node: Node, shared: bool) -> Node:
        node.shared = shared
        await self.db.flush()
        return node

    async def delete_node(self, node_id: uuid.UUID) -> None:
        # Cascade (parent_id, node_content, doc_version FKs) removes descendants + history.
        await self.db.execute(delete(Node).where(Node.id == node_id))

    async def get_descendant_ids(self, node_id: uuid.UUID) -> set[uuid.UUID]:
        sql = """
        WITH RECURSIVE sub(id) AS (
            SELECT id FROM node WHERE parent_id = :nid
            UNION ALL
            SELECT n.id FROM node n JOIN sub s ON n.parent_id = s.id
        ) SELECT id FROM sub
        """
        res = await self.db.execute(sql, {"nid": node_id})
        return {row[0] for row in res.all()}

    # ---- content + versions ----
    async def get_content(self, node_id: uuid.UUID) -> NodeContent | None:
        return (
            await self.db.execute(select(NodeContent).where(NodeContent.node_id == node_id))
        ).scalar_one_or_none()

    async def content_exists(self, node_id: uuid.UUID) -> bool:
        return await self.get_content(node_id) is not None

    async def upsert_content(self, node_id: uuid.UUID, label: str, blocks: list) -> None:
        existing = await self.get_content(node_id)
        if existing:
            existing.label = label
            existing.blocks = blocks
        else:
            self.db.add(NodeContent(node_id=node_id, label=label, blocks=blocks))
        await self.db.flush()

    async def insert_version(
        self, node_id: uuid.UUID, version: int, label: str, blocks: list, edited_by: uuid.UUID
    ) -> None:
        self.db.add(
            DocVersion(node_id=node_id, version=version, label=label, blocks=blocks, edited_by=edited_by)
        )
        await self.db.flush()

    async def list_versions(self, node_id: uuid.UUID) -> list[DocVersion]:
        res = await self.db.execute(
            select(DocVersion)
            .where(DocVersion.node_id == node_id)
            .order_by(DocVersion.version.desc())
        )
        return list(res.scalars().all())

    async def get_version(self, node_id: uuid.UUID, version: int) -> DocVersion | None:
        return (
            await self.db.execute(
                select(DocVersion).where(
                    DocVersion.node_id == node_id, DocVersion.version == version
                )
            )
        ).scalar_one_or_none()
