"""add_source_code_to_repository_functions

Revision ID: 3a7f1c2d8e90
Revises: 1268d9d76ea7
Create Date: 2026-05-11 14:53:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a7f1c2d8e90'
down_revision: Union[str, Sequence[str], None] = '1268d9d76ea7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'repository_functions',
        sa.Column('source_code', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('repository_functions', 'source_code')
