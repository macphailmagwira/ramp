"""add scan_status and scan_progress to connected_repository

Revision ID: 1a2b3c4d5e6f
Revises: 9f1b2c3d4e5f
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, None] = '9f1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('connected_repository', sa.Column('scan_status', sa.String(32), nullable=False, server_default='pending'))
    op.add_column('connected_repository', sa.Column('scan_progress', sa.Integer(), nullable=False, server_default='0'))
    op.create_index(op.f('ix_connected_repository_scan_status'), 'connected_repository', ['scan_status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_connected_repository_scan_status'), table_name='connected_repository')
    op.drop_column('connected_repository', 'scan_progress')
    op.drop_column('connected_repository', 'scan_status')
