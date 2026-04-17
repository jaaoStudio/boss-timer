"""fix boss_types id sequence

Revision ID: 202ad761d3fc
Revises: 254aad421293
Create Date: 2026-04-17 17:45:09.562145

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202ad761d3fc'
down_revision: Union[str, Sequence[str], None] = '254aad421293'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE SEQUENCE IF NOT EXISTS boss_types_id_seq;
        SELECT setval('boss_types_id_seq', (SELECT COALESCE(MAX(id), 0) FROM boss_types));
        ALTER TABLE boss_types ALTER COLUMN id SET DEFAULT nextval('boss_types_id_seq');
        ALTER SEQUENCE boss_types_id_seq OWNED BY boss_types.id;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE boss_types ALTER COLUMN id DROP DEFAULT;
        DROP SEQUENCE IF EXISTS boss_types_id_seq;
    """)
