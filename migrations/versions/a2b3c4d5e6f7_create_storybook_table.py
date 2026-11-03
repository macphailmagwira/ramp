"""create_storybook_table

Revision ID: a2b3c4d5e6f7
Revises: a1f0c3d5e7b9
Create Date: 2026-11-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'a1f0c3d5e7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('storybook',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('connected_repo_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('schema_version', sa.Integer(), nullable=False),
    sa.Column('book', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['connected_repo_id'], ['connected_repository.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_storybook_connected_repo_id'), 'storybook', ['connected_repo_id'], unique=False)
    op.create_index(op.f('ix_storybook_user_id'), 'storybook', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_storybook_user_id'), table_name='storybook')
    op.drop_index(op.f('ix_storybook_connected_repo_id'), table_name='storybook')
    op.drop_table('storybook')
