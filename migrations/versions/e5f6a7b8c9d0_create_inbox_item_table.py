"""create_inbox_item_table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-18 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('inbox_item',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('context', sa.JSON(), nullable=False),
    sa.Column('actor', sa.String(length=200), nullable=False),
    sa.Column('actor_is_ai', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('action', sa.String(length=300), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('unread', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('cleared', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('replies', sa.Integer(), nullable=True),
    sa.Column('preview', sa.Text(), nullable=False),
    sa.Column('activity', sa.JSON(), nullable=False),
    sa.Column('action_label', sa.String(length=100), nullable=False),
    sa.Column('url', sa.String(length=500), nullable=False),
    sa.Column('source_ref', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'source_ref', name='uq_inbox_user_source')
    )
    op.create_index(op.f('ix_inbox_item_user_id'), 'inbox_item', ['user_id'], unique=False)
    op.create_index(op.f('ix_inbox_item_timestamp'), 'inbox_item', ['timestamp'], unique=False)
    op.create_index(op.f('ix_inbox_item_category'), 'inbox_item', ['category'], unique=False)
    op.create_index(op.f('ix_inbox_item_cleared'), 'inbox_item', ['cleared'], unique=False)
    op.create_index(op.f('ix_inbox_item_source_ref'), 'inbox_item', ['source_ref'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_inbox_item_source_ref'), table_name='inbox_item')
    op.drop_index(op.f('ix_inbox_item_cleared'), table_name='inbox_item')
    op.drop_index(op.f('ix_inbox_item_category'), table_name='inbox_item')
    op.drop_index(op.f('ix_inbox_item_timestamp'), table_name='inbox_item')
    op.drop_index(op.f('ix_inbox_item_user_id'), table_name='inbox_item')
    op.drop_table('inbox_item')
