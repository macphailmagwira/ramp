"""add file content and detected framework to repository tables

Revision ID: a1f0c3d5e7b9
Revises: 1a2b3c4d5e6f
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f0c3d5e7b9'
down_revision: Union[str, None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('repository_files', sa.Column('content', sa.Text(), nullable=True))
    op.add_column('connected_repository', sa.Column('framework', sa.String(128), nullable=True))
    op.add_column('connected_repository', sa.Column('tech_stack', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('connected_repository', 'tech_stack')
    op.drop_column('connected_repository', 'framework')
    op.drop_column('repository_files', 'content')
