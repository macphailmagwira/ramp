"""create_architecture_result_table

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('architecture_result',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('connected_repo_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('schema_version', sa.Integer(), nullable=False),
    sa.Column('graph', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['connected_repo_id'], ['connected_repository.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_architecture_result_connected_repo_id'), 'architecture_result', ['connected_repo_id'], unique=False)
    op.create_index(op.f('ix_architecture_result_user_id'), 'architecture_result', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_architecture_result_user_id'), table_name='architecture_result')
    op.drop_index(op.f('ix_architecture_result_connected_repo_id'), table_name='architecture_result')
    op.drop_table('architecture_result')
