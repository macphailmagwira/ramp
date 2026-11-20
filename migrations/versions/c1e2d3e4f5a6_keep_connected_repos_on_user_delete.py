"""Keep connected repositories when their connecting user is deleted.

Revision ID: c1e2d3e4f5a6
Revises: f6a7b8c9d0e1
"""

import sqlalchemy as sa
from alembic import op

revision = "c1e2d3e4f5a6"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "connected_repository",
        "user_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.drop_constraint(
        "connected_repository_user_id_fkey", "connected_repository", type_="foreignkey"
    )
    op.create_foreign_key(
        "connected_repository_user_id_fkey",
        "connected_repository",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "connected_repository_user_id_fkey", "connected_repository", type_="foreignkey"
    )
    op.create_foreign_key(
        "connected_repository_user_id_fkey",
        "connected_repository",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        "DELETE FROM connected_repository WHERE user_id IS NULL"
    )
    op.alter_column(
        "connected_repository",
        "user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
