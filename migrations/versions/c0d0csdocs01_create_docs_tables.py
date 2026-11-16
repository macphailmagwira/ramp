"""Create docs tables: workspace, workspace_member, node, node_content, doc_version.

Revision ID: c0d0csdocs01
Revises: b3c4d5e6f7a8
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c0d0csdocs01"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("icon", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workspace_owner_id", "workspace", ["owner_id"])

    op.create_table(
        "workspace_member",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column(
            "role",
            postgresql.ENUM("owner", "editor", "viewer", name="workspace_role"),
            nullable=False,
        ),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "node",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("node.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "type",
            postgresql.ENUM("folder", "file", name="node_type"),
            nullable=False,
        ),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_node_workspace_id", "node", ["workspace_id"])
    op.create_index("ix_node_parent_id", "node", ["parent_id"])

    op.create_table(
        "node_content",
        sa.Column(
            "node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("node.id", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("blocks", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "doc_version",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("blocks", postgresql.JSONB(), nullable=False),
        sa.Column("edited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_doc_version_node_id", "doc_version", ["node_id"])


def downgrade() -> None:
    op.drop_table("doc_version")
    op.drop_index("ix_node_parent_id")
    op.drop_index("ix_node_workspace_id")
    op.drop_table("node")
    op.drop_table("workspace_member")
    op.drop_table("workspace")
    op.execute("DROP TYPE IF EXISTS node_type")
    op.execute("DROP TYPE IF EXISTS workspace_role")
