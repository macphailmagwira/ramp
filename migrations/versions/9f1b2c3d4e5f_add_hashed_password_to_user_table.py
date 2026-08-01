"""add hashed_password to user table

Revision ID: 9f1b2c3d4e5f
Revises: 3a7f1c2d8e90
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f1b2c3d4e5f'
down_revision: Union[str, None] = '3a7f1c2d8e90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('hashed_password', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'hashed_password')
