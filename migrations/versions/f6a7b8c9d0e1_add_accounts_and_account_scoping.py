"""Add accounts, account membership, and account scoping.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE account_role AS ENUM ('admin', 'member')")

    op.create_table(
        "account",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column(
        "user",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_user_account_id", "user", ["account_id"])
    op.add_column(
        "user",
        sa.Column(
            "account_role",
            postgresql.ENUM(name="account_role", create_type=False),
            server_default="member",
            nullable=False,
        ),
    )

    op.add_column(
        "workspace",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_workspace_account_id", "workspace", ["account_id"])
    op.add_column(
        "workspace",
        sa.Column(
            "connected_repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connected_repository.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_workspace_connected_repository_id", "workspace", ["connected_repository_id"])

    op.add_column(
        "connected_repository",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_connected_repository_account_id", "connected_repository", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_connected_repository_account_id", table_name="connected_repository")
    op.drop_column("connected_repository", "account_id")

    op.drop_index("ix_workspace_connected_repository_id", table_name="workspace")
    op.drop_column("workspace", "connected_repository_id")
    op.drop_index("ix_workspace_account_id", table_name="workspace")
    op.drop_column("workspace", "account_id")

    op.drop_column("user", "account_role")
    op.drop_index("ix_user_account_id", table_name="user")
    op.drop_column("user", "account_id")

    op.drop_table("account")
    op.execute("DROP TYPE IF EXISTS account_role")
