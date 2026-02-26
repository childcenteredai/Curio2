"""add_next_concept_to_messages

Revision ID: fb27e8ae9722
Revises: 7b9f2c1d3e45
Create Date: 2026-02-16 22:47:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fb27e8ae9722'
down_revision = '7b9f2c1d3e45'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add next_concept column to messages table
    op.add_column('messages', sa.Column('next_concept', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove next_concept column from messages table
    op.drop_column('messages', 'next_concept')

