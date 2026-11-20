"""Scope workspaces per repo and allow nodes to be shared globally.

Revision ID: c0d0csdocs03
Revises: c0d0csdocs02
"""

from alembic import op
import sqlalchemy as sa


revision = "c0d0csdocs03"
down_revision = "c0d0csdocs02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace",
        sa.Column("repo", sa.String(512), nullable=True),
    )
    op.create_index("ix_workspace_repo", "workspace", ["repo"])

    op.add_column(
        "node",
        sa.Column(
            "shared",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Application-level default (False) owns future inserts.
    op.alter_column("node", "shared", server_default=None)


def downgrade() -> None:
    op.drop_column("node", "shared")
    op.drop_index("ix_workspace_repo", table_name="workspace")
    op.drop_column("workspace", "repo")
