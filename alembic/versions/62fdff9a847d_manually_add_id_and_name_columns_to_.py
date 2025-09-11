"""Manually add id and name columns to BossType

Revision ID: 62fdff9a847d
Revises: 
Create Date: 2025-09-10 15:40:29.228718

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62fdff9a847d'
down_revision: Union[str, Sequence[str], None] = '27c4e12f2a42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('boss_types', sa.Column('id', sa.Integer(), autoincrement=True, nullable=True))
    op.add_column('boss_types', sa.Column('name_en', sa.String(length=50), nullable=True))
    op.add_column('boss_types', sa.Column('name_zh', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('boss_types', 'name_zh')
    op.drop_column('boss_types', 'name_en')
    op.drop_column('boss_types', 'id')
