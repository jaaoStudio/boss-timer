'''Populate data for new BossType columns and switch primary key

Revision ID: 7a0ebabd50b1
Revises: 62fdff9a847d
Create Date: 2025-09-10 15:50:26.315570

'''
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a0ebabd50b1'
down_revision: Union[str, Sequence[str], None] = '62fdff9a847d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Populate the new name columns from the old boss_name column
    op.execute("UPDATE boss_types SET name_en = boss_name, name_zh = boss_name WHERE name_en IS NULL")

    # Step 2: Populate 'id' for existing boss_types rows
    # Create a temporary sequence to generate IDs for existing rows
    op.execute("CREATE SEQUENCE IF NOT EXISTS boss_types_id_seq_tmp")
    op.execute("UPDATE boss_types SET id = nextval('boss_types_id_seq_tmp') WHERE id IS NULL")
    op.execute("DROP SEQUENCE boss_types_id_seq_tmp")

    # Step 3: Add the new boss_type_id column to boss_records, allowing NULL temporarily
    op.add_column('boss_records', sa.Column('boss_type_id', sa.Integer(), nullable=True))

    # Step 4: Populate the new boss_type_id foreign key column
    # Use a subquery to get the ID from boss_types based on boss_name
    op.execute('''
        UPDATE boss_records
        SET boss_type_id = (SELECT id FROM boss_types WHERE boss_types.boss_name = boss_records.boss_name)
        WHERE boss_type_id IS NULL
    ''')

    # Step 5: Now that data is migrated, make boss_type_id NOT NULL
    op.alter_column('boss_records', 'boss_type_id', nullable=False)

    # Step 6: Drop the old foreign key constraint on boss_records.boss_name
    # Note: The constraint name might be different, you may need to find the correct name in your DB
    op.drop_constraint('boss_records_boss_name_fkey', 'boss_records', type_='foreignkey')

    # Step 7: Drop the old boss_name column from boss_records
    op.drop_column('boss_records', 'boss_name')

    # Step 8: Drop the old primary key constraint on boss_types.boss_name
    # This is now safe as boss_records no longer depends on it
    op.drop_constraint('boss_types_pkey', 'boss_types', type_='primary')

    # Step 9: Set id as new PK for boss_types (it should already have values from autoincrement)
    op.create_primary_key('boss_types_pkey', 'boss_types', ['id'])

    # Step 10: Drop the old boss_name column from boss_types
    op.drop_column('boss_types', 'boss_name')


def downgrade() -> None:
    """Downgrade schema."""
    # This is a complex data migration, a full downgrade is complex and risky.
    # The following is a best-effort attempt to reverse the schema changes.
    # Data loss (the new id relations) is inevitable in a downgrade.

    # Step 10 (reverse): Add boss_name back to boss_types
    op.add_column('boss_types', sa.Column('boss_name', sa.String(length=50), nullable=True))

    # Step 9 (reverse): Drop new PK, restore old PK
    op.drop_constraint('boss_types_pkey', 'boss_types', type_='primary')
    op.create_primary_key('boss_types_pkey', 'boss_types', ['boss_name'])

    # Step 8 (reverse): Add boss_name back to boss_records
    op.add_column('boss_records', sa.Column('boss_name', sa.String(length=50), nullable=True))

    # Step 7 (reverse): Restore foreign key
    op.create_foreign_key('boss_records_boss_name_fkey', 'boss_records', 'boss_types', ['boss_name'], ['boss_name'])

    # Step 6 (reverse): Make boss_type_id nullable again (if needed for data repopulation)
    op.alter_column('boss_records', 'boss_type_id', nullable=True)

    # Step 5 (reverse): Repopulate old boss_name column
    op.execute('''
        UPDATE boss_records
        SET boss_name = (SELECT boss_name FROM boss_types WHERE boss_types.id = boss_records.boss_type_id)
        WHERE boss_name IS NULL
    ''')

    # Step 4 (reverse): Drop the new boss_type_id column
    op.drop_column('boss_records', 'boss_type_id')

    # Step 3 (reverse): Drop new name columns
    op.drop_column('boss_types', 'name_zh')
    op.drop_column('boss_types', 'name_en')
    op.drop_column('boss_types', 'id')
