import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base_class import Base
from src.db.model_mixins import BaseDbModelMixin
from src.features.docs.enums import NodeType, WorkspaceRole


class Workspace(BaseDbModelMixin, Base):
    __tablename__ = "workspace"

    owner_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("account.id", ondelete="CASCADE"), index=True, nullable=False
    )
    connected_repository_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connected_repository.id", ondelete="SET NULL"), index=True, nullable=True
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    repo: Mapped[str | None] = mapped_column(String(512), index=True, nullable=True)


class WorkspaceMember(Base):
    __tablename__ = "workspace_member"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    role: Mapped[WorkspaceRole] = mapped_column(
        SAEnum(
            WorkspaceRole,
            name="workspace_role",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=WorkspaceRole.VIEWER,
        nullable=False,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Node(BaseDbModelMixin, Base):
    __tablename__ = "node"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("node.id", ondelete="CASCADE"), index=True, nullable=True
    )
    type: Mapped[NodeType] = mapped_column(
        SAEnum(NodeType, name="node_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    title: Mapped[str] = mapped_column(
        String(300), nullable=False, default="Title", server_default=text("'Title'")
    )
    version: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    shared: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )


class NodeContent(Base):
    __tablename__ = "node_content"

    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("node.id", ondelete="CASCADE"), primary_key=True
    )
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    blocks: Mapped[list] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DocVersion(Base):
    __tablename__ = "doc_version"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("node.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    blocks: Mapped[list] = mapped_column(JSONB, nullable=False)
    edited_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
