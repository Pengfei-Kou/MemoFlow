"""appsetting KV 表（用户可调设置，如每日新学配额）

Revision ID: f3d8a92c41b7
Revises: 7c6690a1a73b
Create Date: 2026-07-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3d8a92c41b7'
down_revision: Union[str, Sequence[str], None] = '7c6690a1a73b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'appsetting',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('appsetting')
