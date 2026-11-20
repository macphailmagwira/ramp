"""Add title column to node table.

Revision ID: c0d0csdocs02
Revises: c0d0csdocs01
"""

from alembic import op
import sqlalchemy as sa


revision = "c0d0csdocs02"
down_revision = "c0d0csdocs01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "node",
        sa.Column(
            "title",
            sa.String(300),
            nullable=False,
            server_default=sa.text("'Title'"),
        ),
    )
    # Existing rows are now populated with the default; drop the DB-level
    # default so the application-level default ("Title") owns future inserts.
    op.alter_column("node", "title", server_default=None)


def downgrade() -> None:
    op.drop_column("node", "title")
