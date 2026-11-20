"""dedupe_and_unique_architecture_result

Revision ID: d4e5f6a7b8c9
Revises: b3c4d5e6f7a8
Create Date: 2026-11-17 22:08:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c0d0csdocs03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Deduplicate and enforce one row per connected repo."""
    # 1. Keep only the latest row per repo. The window function handles repos
    #    with more than two duplicates and breaks ties deterministically, so we
    #    never end up with two survivors for the same connected_repo_id.
    op.execute(text("""
        DELETE FROM architecture_result
        WHERE id IN (
          SELECT id FROM (
            SELECT id, ROW_NUMBER() OVER (
              PARTITION BY connected_repo_id
              ORDER BY updated_at DESC, id DESC) AS rn
            FROM architecture_result
          ) t WHERE rn > 1
        )
    """))
    # 2. Replace the existing non-unique index with a unique constraint so a
    #    repo can only ever have a single architecture_result row.
    op.drop_index('ix_architecture_result_connected_repo_id', table_name='architecture_result')
    op.create_unique_constraint(
        'uq_architecture_result_connected_repo_id',
        'architecture_result',
        ['connected_repo_id'],
    )


def downgrade() -> None:
    """Revert to a non-unique index, allowing multiple rows per repo again."""
    op.drop_constraint('uq_architecture_result_connected_repo_id', 'architecture_result', type_='unique')
    op.create_index(
        op.f('ix_architecture_result_connected_repo_id'),
        'architecture_result',
        ['connected_repo_id'],
        unique=False,
    )
